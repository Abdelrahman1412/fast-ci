import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from honest_gate import evaluate

SCRIPTS = Path(__file__).resolve().parent.parent


def report(shard, outcomes, reruns=None, durations=None):
    return {
        "shard": shard,
        "outcomes": outcomes,
        "reruns": reruns or {},
        "durations": durations or {},
        "collection_errors": [],
    }


def test_clean_run_passes():
    result = evaluate(["a", "b"], [report(1, {"a": "passed"}), report(2, {"b": "passed"})], "fail")
    assert result["errors"] == []


def test_test_lost_by_the_split_fails():
    result = evaluate(["a", "b", "c"], [report(1, {"a": "passed"}), report(2, {"b": "passed"})], "fail")
    assert result["missing"] == ["c"]
    assert any("never ran: c" in e for e in result["errors"])


def test_test_run_twice_fails():
    result = evaluate(["a"], [report(1, {"a": "passed"}), report(2, {"a": "passed"})], "fail")
    assert result["duplicated"] == ["a"]


def test_uncollected_test_fails():
    result = evaluate(["a"], [report(1, {"a": "passed", "zombie": "passed"})], "fail")
    assert result["unexpected"] == ["zombie"]


def test_missing_shard_report_fails():
    result = evaluate(["a"], [report(1, {"a": "passed"})], "fail", expected_shards=2)
    assert any("expected 2 shard reports" in e for e in result["errors"])


@pytest.mark.parametrize(
    ("policy", "fails", "warns"), [("fail", True, False), ("warn", False, True), ("allow", False, False)]
)
def test_retried_into_green(policy, fails, warns):
    result = evaluate(["a"], [report(1, {"a": "passed"}, reruns={"a": 1})], policy)
    assert result["flaky"] == ["a"]
    assert bool(result["errors"]) is fails
    assert bool(result["warnings"]) is warns


def test_retried_and_still_failing_is_a_failure_not_a_flake():
    result = evaluate(["a"], [report(1, {"a": "failed"}, reruns={"a": 2})], "allow")
    assert result["failed"] == ["a"]
    assert result["flaky"] == []


FLAKY = textwrap.dedent(
    """
    from pathlib import Path

    def test_flaky(tmp_path_factory):
        marker = Path(tmp_path_factory.getbasetemp()).parent / "flaky-attempted"
        if not marker.exists():
            marker.write_text("1")
            raise AssertionError("first attempt fails")
    """
)


def test_end_to_end_pytest_is_green_but_the_gate_is_not(tmp_path):
    """The trap: with retries on, pytest exits 0 for a flaky test. The gate does not."""
    pytest.importorskip("pytest_rerunfailures")
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_flaky.py").write_text(FLAKY)
    (project / "tests" / "test_steady.py").write_text("def test_ok():\n    assert True\n")
    reports = tmp_path / "reports"
    env_path = str(SCRIPTS)
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "pytest_honest",
            "--reruns",
            "2",
            f"--honest-report={reports / 'shard-1.json'}",
            "--basetemp",
            str(tmp_path / "bt"),
            "tests",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": env_path, "PATH": ""},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 rerun" in run.stdout
    collected = tmp_path / "collected.txt"
    collected.write_text("tests/test_flaky.py::test_flaky\ntests/test_steady.py::test_ok\n")
    gate = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "honest_gate.py"),
            "--collected",
            str(collected),
            "--reports",
            str(reports),
            "--reruns-policy",
            "fail",
        ],
        capture_output=True,
        text=True,
    )
    assert gate.returncode == 1, gate.stdout
    assert "passed only after 1 retry(ies): tests/test_flaky.py::test_flaky" in gate.stdout
    data = json.loads((reports / "shard-1.json").read_text())
    assert data["reruns"] == {"tests/test_flaky.py::test_flaky": 1}
