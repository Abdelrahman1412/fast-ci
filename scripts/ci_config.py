#!/usr/bin/env python3
"""Read fast-ci.toml and print the values a workflow needs.

    ci_config.py backend                   # key=value lines
    ci_config.py frontend --event push     # resolves the Playwright lanes too
    ci_config.py backend --github-output   # append to $GITHUB_OUTPUT instead

Lists and tables are printed as compact JSON, ready for ``fromJSON`` in a
workflow. Unknown keys are an error, so a typo cannot silently fall back to a
default.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from fingerprint import fingerprint

DEFAULTS: dict[str, dict] = {
    "backend": {
        "root": "backend",
        "tests": ["tests"],
        "python_files": ["test_*.py"],
        "collection_ignore": [],
        "shards": 4,
        "group_by": "test",
        "reruns": 0,
        "rerun_policy": "fail",
        "durations_artifact": "backend-test-durations",
        "durations_file": ".test_durations.json",
        "migration_inputs": ["migrations/**"],
        "migrate_command": "",
        "postgres_image": "postgres:17",
        "postgres_major": 17,
        "paths": ["**"],
    },
    "frontend": {
        "root": "frontend",
        "vitest_shards": 2,
        "playwright_shards": 2,
        "browsers": ["chromium"],
        "playwright_retries": 0,
        "fail_on_flaky": True,
        "paths": ["**"],
        "lanes": {
            "pull_request": ["mock"],
            "push": ["mock", "full"],
            "schedule": ["mock", "full"],
            "workflow_dispatch": ["mock", "full"],
        },
    },
}
LANES = {"mock", "full"}


class ConfigError(ValueError):
    pass


def load(path: Path, section: str, with_fingerprint: bool = True) -> dict:
    if section not in DEFAULTS:
        raise ConfigError(f"unknown section {section!r}")
    raw = tomllib.loads(path.read_text()).get(section, {})
    unknown = set(raw) - set(DEFAULTS[section])
    if unknown:
        raise ConfigError(f"[{section}] has unknown keys: {', '.join(sorted(unknown))}")
    cfg = {**DEFAULTS[section], **raw}
    if section == "backend":
        if not isinstance(cfg["shards"], int) or not 1 <= cfg["shards"] <= 64:
            raise ConfigError("backend.shards must be an integer from 1 to 64")
        if cfg["group_by"] not in ("test", "file"):
            raise ConfigError("backend.group_by must be 'test' or 'file'")
        if cfg["rerun_policy"] not in ("fail", "warn", "allow"):
            raise ConfigError("backend.rerun_policy must be fail, warn or allow")
        if not isinstance(cfg["reruns"], int) or cfg["reruns"] < 0:
            raise ConfigError("backend.reruns must be a non-negative integer")
        cfg["shard_list"] = list(range(1, cfg["shards"] + 1))
        if with_fingerprint:
            root = path.resolve().parent / cfg["root"]
            try:
                fp = fingerprint(root, cfg["migration_inputs"], f"pg{cfg['postgres_major']}")[0]
            except SystemExit as exc:
                raise ConfigError(f"backend.migration_inputs: {exc}") from None
            cfg["migration_fingerprint"] = fp
    else:
        for key in ("vitest_shards", "playwright_shards"):
            if not isinstance(cfg[key], int) or not 1 <= cfg[key] <= 64:
                raise ConfigError(f"frontend.{key} must be an integer from 1 to 64")
        for event, lanes in cfg["lanes"].items():
            bad = set(lanes) - LANES
            if bad:
                raise ConfigError(f"frontend.lanes.{event} has unknown lanes: {', '.join(sorted(bad))}")
        cfg["vitest_shard_list"] = list(range(1, cfg["vitest_shards"] + 1))
        cfg["playwright_shard_list"] = list(range(1, cfg["playwright_shards"] + 1))
    # dorny/paths-filter takes its filters as YAML text.
    cfg["paths_filter"] = "changed:\n" + "".join(f"  - '{p}'\n" for p in cfg["paths"])
    return cfg


def resolve_lanes(cfg: dict, event: str, override: str = "") -> list[str]:
    if override:
        lanes = [lane.strip() for lane in override.split(",") if lane.strip()]
        bad = set(lanes) - LANES
        if bad:
            raise ConfigError(f"unknown lanes: {', '.join(sorted(bad))}")
        return lanes
    return list(cfg["lanes"].get(event, ["mock"]))


def render(cfg: dict) -> list[str]:
    lines = []
    for key, value in cfg.items():
        if key == "paths_filter":
            lines.append(f"{key}<<EOF_FASTCI\n{value}EOF_FASTCI")
        elif isinstance(value, (list, dict, bool)):
            lines.append(f"{key}={json.dumps(value, separators=(',', ':'))}")
        else:
            lines.append(f"{key}={value}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("section", choices=sorted(DEFAULTS))
    parser.add_argument("--config", type=Path, default=Path("fast-ci.toml"))
    parser.add_argument("--event", default="", help="GitHub event name, for frontend lanes")
    parser.add_argument("--lanes", default="", help="comma-separated lanes that override the event mapping")
    parser.add_argument("--github-output", action="store_true", help="append to $GITHUB_OUTPUT")
    args = parser.parse_args(argv)
    try:
        cfg = load(args.config, args.section)
        if args.section == "frontend":
            lanes = resolve_lanes(cfg, args.event, args.lanes)
            cfg["run_mock"] = "mock" in lanes
            cfg["run_full"] = "full" in lanes
            cfg["active_lanes"] = lanes
    except (ConfigError, tomllib.TOMLDecodeError) as exc:
        print(f"::error title=fast-ci.toml::{exc}")
        return 2
    lines = render(cfg)
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write("\n".join(lines) + "\n")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
