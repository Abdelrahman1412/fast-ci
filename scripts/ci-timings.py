#!/usr/bin/env python3
"""Where does CI time go? Job and step durations for the last N runs of a workflow.

Uses the GitHub CLI (`gh api`), so it works with whatever account `gh` is
logged in as. Read-only.

    scripts/ci-timings.py --repo owner/name --workflow backend.yml --runs 20
    scripts/ci-timings.py --repo owner/name --workflow frontend.yml --branch main --steps 15

It prints, for successful runs:
- run wall clock (first job start to last job end), median and p90;
- per job: median and p90 duration, and how often it ran;
- the slowest steps across all jobs, by median.

Matrix jobs ("test (3)") are grouped by their base name, and the spread
between the fastest and slowest shard of a run is shown: a large spread means
the shards are unbalanced.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime


def gh_api(path: str, attempts: int = 4) -> dict:
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        if attempt == attempts:
            raise SystemExit(f"gh api {path} failed: {proc.stderr.strip()}")
        time.sleep(2 * attempt)  # the API times out now and then; back off and retry
    raise AssertionError("unreachable")


def ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def seconds(start: str | None, end: str | None) -> float | None:
    a, b = ts(start), ts(end)
    return (b - a).total_seconds() if a and b else None


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def fmt(value: float) -> str:
    minutes, secs = divmod(int(round(value)), 60)
    return f"{minutes}m{secs:02d}s"


def base_name(job_name: str) -> str:
    return re.sub(r"\s*\(.*\)$", "", job_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--workflow", required=True, help="workflow file name or id, e.g. backend.yml")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--branch", default="", help="only runs on this branch")
    parser.add_argument("--event", default="", help="only runs from this event, e.g. pull_request")
    parser.add_argument("--steps", type=int, default=10, help="how many slow steps to list")
    parser.add_argument("--json", action="store_true", help="print raw aggregates as JSON")
    args = parser.parse_args(argv)

    query = f"per_page={min(args.runs, 100)}&status=success"
    if args.branch:
        query += f"&branch={args.branch}"
    if args.event:
        query += f"&event={args.event}"
    runs = gh_api(f"repos/{args.repo}/actions/workflows/{args.workflow}/runs?{query}")["workflow_runs"][: args.runs]
    if not runs:
        print("no successful runs found")
        return 1

    walls: list[float] = []
    jobs: dict[str, list[float]] = defaultdict(list)
    spreads: dict[str, list[float]] = defaultdict(list)
    steps: dict[str, list[float]] = defaultdict(list)
    queued: list[float] = []
    for run in runs:
        data = gh_api(f"repos/{args.repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
        starts = [j["started_at"] for j in data if j.get("started_at") and j.get("conclusion") != "skipped"]
        ends = [j["completed_at"] for j in data if j.get("completed_at") and j.get("conclusion") != "skipped"]
        if starts and ends:
            walls.append(seconds(min(starts), max(ends)) or 0.0)
        per_run: dict[str, list[float]] = defaultdict(list)
        for job in data:
            if job.get("conclusion") == "skipped":
                continue
            duration = seconds(job.get("started_at"), job.get("completed_at"))
            if duration is None:
                continue
            name = base_name(job["name"])
            jobs[name].append(duration)
            per_run[name].append(duration)
            wait = seconds(job.get("created_at"), job.get("started_at"))
            if wait is not None:
                queued.append(wait)
            for step in job.get("steps", []):
                step_time = seconds(step.get("started_at"), step.get("completed_at"))
                if step_time is not None and step.get("conclusion") != "skipped":
                    steps[f"{name} > {step['name']}"].append(step_time)
        for name, values in per_run.items():
            if len(values) > 1:
                spreads[name].append(max(values) - min(values))

    if args.json:
        print(json.dumps({"walls": walls, "jobs": jobs, "steps": steps, "spreads": spreads}, indent=1))
        return 0

    print(f"{args.workflow}: {len(runs)} successful run(s)")
    print(f"wall clock   median {fmt(statistics.median(walls))}   p90 {fmt(pct(walls, 0.9))}")
    if queued:
        print(f"queue wait   median {fmt(statistics.median(queued))}   p90 {fmt(pct(queued, 0.9))} (per job)")
    print()
    print(f"{'job':<40} {'runs':>5} {'median':>8} {'p90':>8} {'shard spread':>13}")
    for name, values in sorted(jobs.items(), key=lambda kv: -statistics.median(kv[1])):
        spread = f"{fmt(statistics.median(spreads[name]))}" if spreads.get(name) else "-"
        print(
            f"{name[:40]:<40} {len(values):>5} {fmt(statistics.median(values)):>8} {fmt(pct(values, 0.9)):>8} "
            f"{spread:>13}"
        )
    print()
    print("slowest steps (median over runs where they ran)")
    ranked = sorted(steps.items(), key=lambda kv: -statistics.median(kv[1]))[: args.steps]
    for name, values in ranked:
        print(f"  {fmt(statistics.median(values)):>7}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
