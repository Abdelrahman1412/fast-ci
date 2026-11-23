import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
GOOD = "def test_ok():\n    assert True\n"


def make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "project"
    for name, body in {"tests/test_good.py": GOOD, **files}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    (root / "pytest.ini").write_text("[pytest]\npython_files = test_*.py\n")
    return root


def guard(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "check_collection.py"),
            "--root",
            str(root),
            "--tests",
            "tests",
            "--pytest",
            f"{sys.executable} -m pytest",
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def test_clean_project_passes(tmp_path):
    result = guard(make_project(tmp_path, {"tests/helpers.py": "def build():\n    return 1\n"}))
    assert result.returncode == 0, result.stdout
    assert "every test file is collected" in result.stdout


@pytest.mark.parametrize("name", ["tests/employees_test.py", "tests/unit/check_payroll.py", "tests/testLeave.py"])
def test_misnamed_file_is_caught(tmp_path, name):
    result = guard(make_project(tmp_path, {name: GOOD}))
    assert result.returncode == 1
    assert f"{name}: defines tests but its name does not match test_*.py" in result.stdout


def test_import_error_is_caught_even_when_pytest_is_told_to_continue(tmp_path):
    result = guard(make_project(tmp_path, {"tests/test_broken.py": "import not_a_module\n" + GOOD}))
    assert result.returncode == 1
    assert "tests/test_broken.py: import failed during collection" in result.stdout


def test_module_level_skip_is_caught(tmp_path):
    body = "import pytest\npytest.importorskip('not_a_module')\n" + GOOD
    result = guard(make_project(tmp_path, {"tests/test_optional.py": body}))
    assert result.returncode == 1
    assert "tests/test_optional.py: the whole module was skipped" in result.stdout


def test_ignore_list_allows_deliberate_exceptions(tmp_path):
    result = guard(make_project(tmp_path, {"tests/examples/sample_check.py": GOOD}), "--ignore", "tests/examples/*")
    assert result.returncode == 0, result.stdout


def test_ignored_test_modules_are_not_collected(tmp_path):
    # A suite that runs in its own job (here: a schema fuzzer) must not leak into the shard files.
    out = tmp_path / "collected.txt"
    project = make_project(tmp_path, {"tests/fuzz/test_api_fuzz.py": GOOD})
    result = guard(project, "--ignore", "tests/fuzz/*", "--out", str(out))
    assert result.returncode == 0, result.stdout
    assert out.read_text() == "tests/test_good.py::test_ok\n"


def test_writes_collected_node_ids(tmp_path):
    out = tmp_path / "collected.txt"
    result = guard(make_project(tmp_path, {}), "--out", str(out))
    assert result.returncode == 0
    assert out.read_text() == "tests/test_good.py::test_ok\n"
