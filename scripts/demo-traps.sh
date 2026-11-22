#!/usr/bin/env bash
# Plant each trap in the demo backend and show the guard that catches it.
# Everything planted is removed on exit. Needs Postgres (PGHOST/PGPORT/PGUSER).
#
#   scripts/demo-traps.sh
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo/backend" || exit 1
work=$(mktemp -d)
planted=()
# shellcheck disable=SC2329  # called by the EXIT trap
cleanup() { rm -f "${planted[@]}"; rm -rf "$work"; }
trap cleanup EXIT

py="uv run python"
status=0
expect() { # expect <wanted-exit> <got-exit> <label>
  if [ "$1" = "$2" ]; then echo "  -> as expected (exit $2): $3"; else echo "  -> UNEXPECTED exit $2 (wanted $1): $3"; status=1; fi
}

echo "== 1. A test file with the wrong name"
cp tests/unit/test_leave_days.py tests/unit/leave_days_checks.py
planted+=("$repo/backend/tests/unit/leave_days_checks.py")
$py ../scripts/check_collection.py --root . --tests tests --pytest "uv run python -m pytest"
expect 1 $? "collection guard names the file pytest would never open"
rm -f tests/unit/leave_days_checks.py

echo
echo "== 2. A whole module skipped by a missing optional import"
printf 'import pytest\npytest.importorskip("a_package_nobody_installed")\n\ndef test_export():\n    assert True\n' \
  > tests/unit/test_export_optional.py
planted+=("$repo/backend/tests/unit/test_export_optional.py")
$py ../scripts/check_collection.py --root . --tests tests --pytest "uv run python -m pytest"
expect 1 $? "collection guard flags the silently skipped module"
rm -f tests/unit/test_export_optional.py

echo
echo "== 3. A flaky test retried into green"
cat > tests/unit/test_flaky_demo.py <<'PY'
import os
from pathlib import Path

def test_payslip_pdf_renders():
    marker = Path(os.environ["FLAKY_MARKER"])
    if not marker.exists():
        marker.write_text("attempted")
        raise AssertionError("timed out waiting for the renderer")
PY
planted+=("$repo/backend/tests/unit/test_flaky_demo.py")
FLAKY_MARKER="$work/marker" uv run pytest -q tests/unit/test_flaky_demo.py tests/unit/test_leave_days.py \
  --reruns 2 --honest-report="$work/reports/shard-1.json" -p no:cacheprovider | tail -2
expect 0 "${PIPESTATUS[0]}" "pytest alone reports green"
$py ../scripts/check_collection.py --root . --tests tests --pytest "uv run python -m pytest" --out "$work/all.txt" >/dev/null
grep -E '^tests/unit/(test_flaky_demo|test_leave_days)\.py::' "$work/all.txt" > "$work/collected.txt"
$py ../scripts/honest_gate.py --collected "$work/collected.txt" --reports "$work/reports" --reruns-policy fail \
  | grep -E 'retry|honest gate'
expect 1 "${PIPESTATUS[0]}" "honest gate fails the run"
rm -f tests/unit/test_flaky_demo.py

echo
echo "== 4. A cached database dump that no longer matches the migrations"
fp=$(python3 ../scripts/fingerprint.py --root . 'migrations/*.sql' app/migrate.py --salt pg17)
export FASTCI_BASE_DB=fastci_demo_base FASTCI_DUMP="$work/base.dump" FASTCI_MIGRATE_CMD="uv run python -m app.migrate"
FASTCI_FINGERPRINT=$fp ../scripts/test_db.sh build
FASTCI_FINGERPRINT=$fp ../scripts/test_db.sh restore
expect 0 $? "restore with the matching fingerprint"
echo "-- 0005_add_column.sql lands; the old dump is offered again"
FASTCI_FINGERPRINT=$(echo "$fp-0005" | sha256sum | cut -c1-20) ../scripts/test_db.sh restore
expect 3 $? "restore refuses the stale dump"
psql -q -d postgres -c "DROP DATABASE IF EXISTS fastci_demo_base WITH (FORCE)"

echo
if [ $status -eq 0 ]; then echo "all four traps were caught"; else echo "a guard did not behave as expected"; fi
exit $status
