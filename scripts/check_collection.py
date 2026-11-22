#!/usr/bin/env python3
"""Fail when a test file exists but pytest never collects a test from it.

Three ways tests silently stop running:

1. The file name does not match ``python_files`` (``employees_test.py`` when
   only ``test_*.py`` is collected). pytest never opens it.
2. The module raises on import and someone "fixed" the red run with
   ``--continue-on-collection-errors``, or a ``try: import`` that skips.
3. A module-level ``pytest.skip``/``importorskip`` turns the whole file into
   one quiet "s".

This script finds every Python file under the test roots that *defines* tests
(``def test_*`` or ``class Test*``, read with ``ast``, so nothing is imported),
runs ``pytest --collect-only`` with the ``pytest_honest`` plugin, and compares.

    check_collection.py --root backend --tests tests --out collected.txt
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def defines_tests(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        return True  # it is meant to be code; let pytest report the error
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            return True
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True
    return False


def candidate_files(root: Path, test_dirs: list[str], ignore: list[str]) -> set[str]:
    found: set[str] = set()
    for test_dir in test_dirs:
        for path in (root / test_dir).rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if path.name == "conftest.py" or any(fnmatch.fnmatch(rel, pat) for pat in ignore):
                continue
            if defines_tests(path):
                found.add(rel)
    return found


def collect(root: Path, test_dirs: list[str], pytest_cmd: list[str], extra: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "collect.json"
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(HERE), os.environ.get("PYTHONPATH")]))}
        cmd = [
            *pytest_cmd,
            "--collect-only",
            "-q",
            "-p",
            "pytest_honest",
            f"--honest-report={report}",
            "--continue-on-collection-errors",
            *extra,
            *test_dirs,
        ]
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        if not report.exists():
            sys.stdout.write(proc.stdout + proc.stderr)
            raise SystemExit("check_collection: pytest did not produce a report (see output above)")
        data = json.loads(report.read_text())
        data["pytest_output"] = proc.stdout + proc.stderr
        return data


def matches_python_files(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."), help="directory pytest runs from")
    parser.add_argument("--tests", nargs="+", default=["tests"], help="test roots, relative to --root")
    parser.add_argument("--python-files", nargs="+", default=["test_*.py"], help="pytest's python_files patterns")
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="glob patterns of files that may define tests but are not meant to be collected",
    )
    parser.add_argument("--pytest", default=f"{sys.executable} -m pytest", help="command that runs pytest")
    parser.add_argument("--out", type=Path, help="write the collected node ids here, one per line")
    parser.add_argument("pytest_args", nargs="*", help="extra arguments for pytest (after --)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    data = collect(root, args.tests, args.pytest.split(), args.pytest_args)
    collected: list[str] = data["collected"]
    collected_files = {nodeid.split("::", 1)[0] for nodeid in collected}
    candidates = candidate_files(root, args.tests, args.ignore)

    problems: list[str] = []
    for error in data["collection_errors"]:
        problems.append(f"{error}: import failed during collection")
    for module, reason in sorted(data["module_skips"].items()):
        problems.append(f"{module}: the whole module was skipped ({reason.strip()})")
    for path in sorted(candidates - collected_files - set(data["collection_errors"]) - set(data["module_skips"])):
        if not matches_python_files(Path(path).name, args.python_files):
            problems.append(f"{path}: defines tests but its name does not match {' or '.join(args.python_files)}")
        else:
            problems.append(f"{path}: defines tests but none were collected")

    print(
        f"collection guard: {len(collected)} tests from {len(collected_files)} files; "
        f"{len(candidates)} files define tests"
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(f"{nodeid}\n" for nodeid in collected))
    if not collected:
        problems.append("no tests were collected at all")
    if problems:
        for problem in problems:
            print(f"::error title=Test never runs::{problem}")
        print(f"collection guard: FAILED, {len(problems)} file(s) would never run")
        return 1
    print("collection guard: every test file is collected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
