#!/usr/bin/env bash
# Run the backend pipeline the way CI does, on your machine:
# template database -> collection guard -> duration split -> shards -> honest gate.
#
#   scripts/local-ci.sh              # shards one after another, timing each
#   scripts/local-ci.sh --parallel   # shards at the same time, like CI runners
#
# Reads fast-ci.toml. Needs Postgres (PGHOST/PGPORT/PGUSER) and uv.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
parallel=false
[ "${1:-}" = "--parallel" ] && parallel=true
out="$repo/.cache/local-ci"
rm -rf "$out" && mkdir -p "$out/reports"

cfg() { python3 "$repo/scripts/ci_config.py" backend --config "$repo/fast-ci.toml" | sed -n "s/^$1=//p"; }
shards=$(cfg shards)
group_by=$(cfg group_by)
reruns=$(cfg reruns)
policy=$(cfg rerun_policy)
durations="$repo/backend/$(cfg durations_file)"
ms() { echo $(( $(date +%s%N) / 1000000 )); }

cd "$repo/backend"
uv sync --frozen --quiet

echo "== template database"
FASTCI_FINGERPRINT=$(cfg migration_fingerprint) FASTCI_MIGRATE_CMD=$(cfg migrate_command) \
  FASTCI_DUMP="$repo/.cache/test-db/base.dump" "$repo/scripts/test_db.sh" ensure

echo "== collection guard"
uv run python "$repo/scripts/check_collection.py" --root . --tests tests --pytest "uv run python -m pytest" \
  --out "$out/collected.txt"

echo "== split ($shards shards by $group_by)"
python3 "$repo/scripts/split_tests.py" --tests "$out/collected.txt" --durations "$durations" \
  --shards "$shards" --group-by "$group_by" --out "$out/shards"

echo "== shards ($([ "$parallel" = true ] && echo parallel || echo one after another))"
run_shard() {
  local i=$1 start
  start=$(ms)
  if FASTCI_SHARD=$i FASTCI_REQUIRE_TEMPLATE=1 uv run pytest -q -p no:cacheprovider "@$out/shards/shard-$i.txt" \
    --reruns "$reruns" --honest-report="$out/reports/shard-$i.json" > "$out/shard-$i.log" 2>&1; then
    echo "shard $i: $(tail -1 "$out/shard-$i.log") [wall $(( $(ms) - start )) ms]"
  else
    echo "shard $i: FAILED [wall $(( $(ms) - start )) ms], see $out/shard-$i.log"
  fi
}
total_start=$(ms)
if [ "$parallel" = true ]; then
  for i in $(seq 1 "$shards"); do run_shard "$i" & done
  wait
else
  for i in $(seq 1 "$shards"); do run_shard "$i"; done
fi
echo "all shards: $(( $(ms) - total_start )) ms"

echo "== honest gate"
python3 "$repo/scripts/honest_gate.py" --collected "$out/collected.txt" --reports "$out/reports" \
  --reruns-policy "$policy" --expected-shards "$shards" --durations-out "$out/test_durations.json"
