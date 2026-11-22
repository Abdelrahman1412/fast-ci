"""pytest plugin: write down what actually ran, so CI can check it.

Load it with ``-p pytest_honest`` (the scripts/ folder must be importable) and
pass ``--honest-report=path.json``. The report holds:

- ``collected``: node ids selected to run in this process
- ``outcomes``: final outcome per node id (passed / failed / skipped / error)
- ``reruns``: how many times each retried test was re-run
- ``durations``: seconds per node id (setup + call + teardown of the last attempt)
- ``collection_errors``: files pytest could not import
- ``empty_modules``: test modules that produced no tests (module-level skip,
  swallowed import error, everything parametrized away)

``honest_gate.py`` reads these reports from every shard and decides.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("honest")
    group.addoption("--honest-report", default=None, help="write the run record to this JSON file")


def pytest_configure(config: pytest.Config) -> None:
    path = config.getoption("--honest-report")
    if path and not hasattr(config, "workerinput"):
        config.pluginmanager.register(Recorder(Path(path)), "honest-recorder")


class Recorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.collected: list[str] = []
        self.outcomes: dict[str, str] = {}
        self.reruns: dict[str, int] = defaultdict(int)
        self.durations: dict[str, float] = defaultdict(float)
        self.collection_errors: list[str] = []
        self.module_items: dict[str, int] = {}
        self.module_skips: dict[str, str] = {}

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if not isinstance(report.nodeid, str) or not report.nodeid.endswith(".py"):
            return
        if report.failed:
            self.collection_errors.append(report.nodeid)
        elif report.skipped:
            reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
            self.module_skips[report.nodeid] = reason
        else:
            self.module_items.setdefault(report.nodeid, 0)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        self.collected = [item.nodeid for item in items]
        per_module: dict[str, int] = defaultdict(int)
        for item in items:
            per_module[item.nodeid.split("::", 1)[0]] += 1
        for module in self.module_items:
            self.module_items[module] = per_module.get(module, 0)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid = report.nodeid
        if report.outcome == "rerun":
            self.reruns[nodeid] += 1
            self.durations[nodeid] = 0.0
            return
        if report.when == "setup":
            self.durations[nodeid] = 0.0
        self.durations[nodeid] += report.duration
        if report.when == "call":
            self.outcomes[nodeid] = "skipped" if report.skipped else report.outcome
        elif report.failed:
            self.outcomes[nodeid] = "error"
        elif report.skipped and report.when == "setup":
            self.outcomes[nodeid] = "skipped"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        empty = sorted(m for m, n in self.module_items.items() if n == 0)
        record = {
            "shard": os.environ.get("FASTCI_SHARD", "local"),
            "exitstatus": int(exitstatus),
            "collected": self.collected,
            "outcomes": self.outcomes,
            "reruns": dict(self.reruns),
            "durations": {k: round(v, 4) for k, v in self.durations.items()},
            "collection_errors": self.collection_errors,
            "empty_modules": empty,
            "module_skips": self.module_skips,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
