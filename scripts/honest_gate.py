#!/usr/bin/env python3
"""Decide whether a sharded test run really passed.

Reads the ``pytest_honest`` report of every shard plus the list of collected
tests, then fails on any of:

- a collected test that ran in no shard (lost by the split);
- a test that ran in two shards (wasted, and hides order dependence);
- a test that ran but was never collected (the shard files are stale);
- a failed test or a collection error;
- a test that passed only after a retry, when ``--reruns-policy fail``.
  With ``warn`` it is reported loudly but does not fail; with ``allow`` it is
  only counted.

It also merges every shard's durations into one file for the next split.

    honest_gate.py --collected collected.txt --reports reports/ --reruns-policy fail \\
        --durations-out .test_durations.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


def load_reports(folder: Path) -> list[dict]:
    reports = [json.loads(p.read_text()) for p in sorted(folder.rglob("*.json"))]
    if not reports:
        raise SystemExit(f"honest_gate: no shard reports under {folder}")
    return reports


def evaluate(collected: list[str], reports: list[dict], policy: str, expected_shards: int | None = None) -> dict:
    ran = Counter()
    outcomes: dict[str, str] = {}
    reruns: dict[str, int] = {}
    durations: dict[str, float] = {}
    collection_errors: list[str] = []
    for report in reports:
        for nodeid, outcome in report["outcomes"].items():
            ran[nodeid] += 1
            outcomes[nodeid] = outcome
        reruns.update(report.get("reruns", {}))
        durations.update(report.get("durations", {}))
        collection_errors.extend(report.get("collection_errors", []))

    expected = set(collected)
    flaky = sorted(n for n, count in reruns.items() if count and outcomes.get(n) == "passed")
    result = {
        "shards": len(reports),
        "collected": len(expected),
        "ran": len(ran),
        "missing": sorted(expected - set(ran)),
        "duplicated": sorted(n for n, c in ran.items() if c > 1),
        "unexpected": sorted(set(ran) - expected),
        "failed": sorted(n for n, o in outcomes.items() if o in ("failed", "error")),
        "skipped": sorted(n for n, o in outcomes.items() if o == "skipped"),
        "flaky": flaky,
        "rerun_counts": {n: reruns[n] for n in flaky},
        "collection_errors": sorted(set(collection_errors)),
        "durations": durations,
    }
    errors: list[str] = []
    warnings: list[str] = []
    if expected_shards is not None and len(reports) != expected_shards:
        errors.append(f"expected {expected_shards} shard reports, found {len(reports)}")
    for nodeid in result["missing"]:
        errors.append(f"never ran: {nodeid}")
    for nodeid in result["duplicated"]:
        errors.append(f"ran in more than one shard: {nodeid}")
    for nodeid in result["unexpected"]:
        errors.append(f"ran but was not collected (stale shard list?): {nodeid}")
    for nodeid in result["collection_errors"]:
        errors.append(f"collection error: {nodeid}")
    for nodeid in result["failed"]:
        errors.append(f"failed: {nodeid}")
    for nodeid in flaky:
        message = f"passed only after {reruns[nodeid]} retry(ies): {nodeid}"
        if policy == "fail":
            errors.append(message)
        elif policy == "warn":
            warnings.append(message)
    result["errors"] = errors
    result["warnings"] = warnings
    return result


def summary_markdown(result: dict, reports: list[dict], policy: str) -> str:
    lines = ["### Honest CI gate", "", "| shard | tests | seconds | reruns |", "|---:|---:|---:|---:|"]
    for report in sorted(reports, key=lambda r: str(r.get("shard"))):
        seconds = sum(report.get("durations", {}).values())
        lines.append(
            f"| {report.get('shard')} | {len(report['outcomes'])} | {seconds:.1f} | "
            f"{sum(report.get('reruns', {}).values())} |"
        )
    lines += [
        "",
        f"Collected {result['collected']}, ran {result['ran']}, skipped {len(result['skipped'])}, "
        f"failed {len(result['failed'])}, passed only on retry {len(result['flaky'])} (policy: {policy}).",
    ]
    if result["errors"]:
        lines += ["", "**Failed because:**", ""] + [f"- `{e}`" for e in result["errors"][:50]]
    if result["warnings"]:
        lines += ["", "**Flaky (not failing the run, policy is warn):**", ""] + [f"- `{w}`" for w in result["warnings"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collected", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True, help="folder holding every shard's report")
    parser.add_argument("--reruns-policy", choices=["fail", "warn", "allow"], default="fail")
    parser.add_argument("--expected-shards", type=int)
    parser.add_argument("--durations-out", type=Path, help="write the merged durations here")
    args = parser.parse_args(argv)

    collected = [line.strip() for line in args.collected.read_text().splitlines() if line.strip()]
    reports = load_reports(args.reports)
    result = evaluate(collected, reports, args.reruns_policy, args.expected_shards)

    if args.durations_out:
        args.durations_out.write_text(json.dumps(dict(sorted(result["durations"].items())), indent=1) + "\n")
    summary = summary_markdown(result, reports, args.reruns_policy)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(summary)
    print(summary)
    for warning in result["warnings"]:
        print(f"::warning title=Flaky test::{warning}")
    for error in result["errors"]:
        print(f"::error title=Honest CI gate::{error}")
    if result["errors"]:
        print(f"honest gate: FAILED ({len(result['errors'])} problem(s))")
        return 1
    print("honest gate: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
