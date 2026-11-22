#!/usr/bin/env python3
"""One required check for branch protection: did every job that should run, pass?

GitHub treats a skipped required job as passing, and a workflow that never
starts (filtered out by ``paths:``) leaves a required check pending forever.
So branch protection should require exactly one job that always runs
(``if: always()``) and judges the others. Pass it the ``needs`` context:

    env:
      NEEDS: ${{ toJSON(needs) }}
    run: python3 scripts/ci_result.py --plan plan --may-skip e2e-full

Rules:
- any job that failed or was cancelled fails the result;
- the plan job must succeed;
- if the plan says nothing relevant changed (output ``run`` is ``false``),
  every other job must be skipped;
- otherwise a skipped job fails the result unless it is listed in --may-skip.
  A job skipped because its dependency failed is the classic false green.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def judge(needs: dict, plan: str, may_skip: set[str]) -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = True
    if plan not in needs:
        return False, [f"plan job {plan!r} is not in needs"]
    plan_job = needs[plan]
    should_run = plan_job.get("outputs", {}).get("run", "true") == "true"
    if plan_job["result"] != "success":
        ok = False
        lines.append(f"FAIL  {plan}: {plan_job['result']} (the plan job must succeed)")
    else:
        lines.append(f"ok    {plan}: success (run={'true' if should_run else 'false'})")
    for name, job in needs.items():
        if name == plan:
            continue
        result = job["result"]
        if result in ("failure", "cancelled"):
            ok = False
            lines.append(f"FAIL  {name}: {result}")
        elif result == "skipped":
            if should_run and name not in may_skip:
                ok = False
                lines.append(f"FAIL  {name}: skipped, but the plan said it should run")
            else:
                lines.append(f"ok    {name}: skipped ({'allowed' if should_run else 'nothing relevant changed'})")
        elif result == "success":
            lines.append(f"ok    {name}: success")
        else:
            ok = False
            lines.append(f"FAIL  {name}: unexpected result {result!r}")
    return ok, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", default="plan", help="job whose outputs.run says whether work was needed")
    parser.add_argument("--may-skip", default="", help="comma-separated jobs that may be skipped when run=true")
    args = parser.parse_args(argv)
    needs = json.loads(os.environ["NEEDS"])
    ok, lines = judge(needs, args.plan, {n.strip() for n in args.may_skip.split(",") if n.strip()})
    print("\n".join(lines))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write("### CI result\n\n```\n" + "\n".join(lines) + "\n```\n")
    print("CI result: " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
