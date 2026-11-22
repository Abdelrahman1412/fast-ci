#!/usr/bin/env python3
"""Split collected tests into N shards of equal *time*, not equal count.

Reads the collected node ids (from check_collection.py) and a durations file
({node id: seconds}). Tests the durations file does not know get the median
duration, so a stale file costs balance, never correctness.

Assignment is longest-first onto the least-loaded shard (LPT). With
``--group-by file`` whole files stay together, which keeps module-scoped
fixtures cheap but lets one slow file decide the wall clock. The script warns
when that happens.

Writes ``shard-<i>.txt`` files that pytest reads with ``pytest @shard-1.txt``.

    split_tests.py --tests collected.txt --durations .test_durations.json --shards 4 --out shards/
"""

from __future__ import annotations

import argparse
import heapq
import json
import statistics
from collections import defaultdict
from pathlib import Path


def load_durations(path: Path | None) -> dict[str, float]:
    if path is None or not path.exists():
        return {}
    return {k: float(v) for k, v in json.loads(path.read_text()).items()}


def split(
    tests: list[str], durations: dict[str, float], shards: int, group_by: str = "test"
) -> tuple[list[list[str]], list[float], dict]:
    if shards < 1:
        raise ValueError("shards must be at least 1")
    known = [durations[t] for t in tests if t in durations]
    default = statistics.median(known) if known else 1.0
    units: dict[str, list[str]] = defaultdict(list)
    for test in tests:
        key = test.split("::", 1)[0] if group_by == "file" else test
        units[key].append(test)
    weight = {key: sum(durations.get(t, default) for t in members) for key, members in units.items()}

    heap = [(0.0, i) for i in range(shards)]
    buckets: list[list[str]] = [[] for _ in range(shards)]
    totals = [0.0] * shards
    for key in sorted(units, key=lambda k: (-weight[k], k)):
        total, i = heapq.heappop(heap)
        buckets[i].extend(units[key])
        totals[i] = total + weight[key]
        heapq.heappush(heap, (totals[i], i))

    ideal = sum(weight.values()) / shards
    heaviest = max(weight, key=weight.get) if weight else None
    info = {
        "unknown": sum(1 for t in tests if t not in durations),
        "default": default,
        "ideal": ideal,
        "heaviest_unit": heaviest,
        "heaviest_seconds": weight.get(heaviest, 0.0) if heaviest else 0.0,
    }
    return buckets, totals, info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests", type=Path, required=True, help="file with one node id per line")
    parser.add_argument("--durations", type=Path, help="JSON map of node id to seconds")
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--group-by", choices=["test", "file"], default="test")
    parser.add_argument("--out", type=Path, required=True, help="directory for shard-<i>.txt")
    args = parser.parse_args(argv)

    tests = [line.strip() for line in args.tests.read_text().splitlines() if line.strip()]
    durations = load_durations(args.durations)
    buckets, totals, info = split(tests, durations, args.shards, args.group_by)

    args.out.mkdir(parents=True, exist_ok=True)
    for i, bucket in enumerate(buckets, start=1):
        (args.out / f"shard-{i}.txt").write_text("".join(f"{t}\n" for t in bucket))

    print(
        f"split {len(tests)} tests into {args.shards} shards by {args.group_by} "
        f"({info['unknown']} without a recorded duration, given {info['default'] * 1000:.1f} ms each)"
    )
    print(f"{'shard':>5}  {'tests':>5}  {'seconds':>8}")
    for i, (bucket, total) in enumerate(zip(buckets, totals, strict=True), start=1):
        print(f"{i:>5}  {len(bucket):>5}  {total:>8.2f}")
    spread = (max(totals) - min(totals)) if totals else 0.0
    print(f"ideal {info['ideal']:.2f}s per shard; slowest {max(totals):.2f}s; spread {spread:.2f}s")
    if args.shards > 1 and info["heaviest_seconds"] > info["ideal"]:
        print(
            f"::warning title=One unit dominates a shard::{info['heaviest_unit']} alone takes "
            f"{info['heaviest_seconds']:.2f}s, more than an even shard ({info['ideal']:.2f}s). "
            f"Split it, or use --group-by test."
        )
    empty = [i for i, b in enumerate(buckets, start=1) if not b]
    if empty:
        print(f"::warning title=Empty shards::shards {empty} got no tests; lower the shard count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
