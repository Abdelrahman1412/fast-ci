# fast-ci

Fast CI that does not lie. Reusable GitHub Actions patterns for a Python +
Postgres backend and a TypeScript + Playwright frontend, each one proven on a
small working demo.

## The problem

A slow CI changes how a team works. When a pull request takes 45 minutes to go
green, people batch changes, stop waiting for results, and merge on "it
passed last time". Reviews pile up. Hotfixes wait behind the queue.

The usual fixes make it worse in a quieter way. Retries are added until the
flaky tests stop showing. Jobs are skipped when a path did not change, and a
skipped job counts as passed. A test file with the wrong name never runs, and
nobody notices, because nothing failed.

So there are two problems: CI is slow, and its green does not mean what people
think it means.

## Before and after

| Before | After |
|---|---|
| Every shard runs every migration from scratch. | One job builds the database, caches a dump keyed on the migrations, and each shard restores it in seconds. A stale dump is refused, not trusted. |
| Shards split by file or by count. One slow file decides the wall clock. | Shards split by recorded test duration. The slowest shard is close to the average. |
| The full browser suite blocks every pull request. | Pull requests run the mocked-API lane. The full end-to-end lane runs on merge and nightly. Which lane runs when is one line of config. |
| Every shard rebuilds the app. | The app is built once and handed to every shard. |
| A test retried into green is a green test. | A test that passes only on retry fails the run (or is reported loudly, if you choose). |
| A misnamed or broken test file silently runs nothing. | CI fails and names the file that would never run. |
| Branch protection lists ten checks; a skipped one counts as passed. | One required check, `CI result`, that fails on any failure or any skip the plan did not intend. |

What it changes for a team: feedback arrives while the author still has the
change in their head. A green run can be trusted, so reviewers stop
re-running jobs "to be sure". Flaky tests get a name and an owner instead of
a retry. Adding shards is a config change, not a branch-protection change.

## What is in the box

| Path | What it is |
|---|---|
| `fast-ci.toml` | The one config file. Shard counts, retry policy, lanes per trigger, cache inputs, path filters. |
| `.github/workflows/backend.yml` | plan → test-db + collect → sharded tests → honest gate → CI result |
| `.github/workflows/frontend.yml` | plan → build once → Vitest shards + Playwright shards (merged report) → CI result |
| `.github/workflows/unsharded.yml` | Manual single-job baseline for timing comparisons. |
| `.github/actions/` | Composite actions: uv setup, pnpm setup, migrated test database. |
| `scripts/` | The tools the workflows call. Each one runs locally too. |
| `backend/` | Demo HR service: FastAPI + Postgres, 390 tests, some deliberately DB-heavy. |
| `frontend/` | Demo HR web app: Vite + TypeScript, 223 Vitest tests, Playwright mock and full lanes. |
| `docs/playbook.md` | How to profile a slow CI, each technique with when it helps and when it does not, and the traps. |

The scripts:

| Script | Job |
|---|---|
| `fingerprint.py`, `test_db.sh` | Hash every input of the test schema; build, dump, restore and verify the template database. |
| `check_collection.py` | Fail when a file defines tests that pytest never collects (bad name, import error, module-level skip). |
| `split_tests.py` | Split collected tests into shards of equal duration. Warn when one file is longer than a whole shard. |
| `pytest_honest.py` | pytest plugin: record what each shard collected, ran, retried and how long it took. |
| `honest_gate.py` | Prove the shards together ran exactly the collected tests; apply the retry policy; merge durations. |
| `ci_result.py` | The single required check. |
| `check-specs.mjs`, `check-playwright-run.mjs` | The same two guards for Playwright. |
| `ci-timings.py` | Pull job and step durations of the last N runs through `gh api` and show where the time goes. |
| `local-ci.sh` | Run the backend pipeline locally, exactly as CI does. |
| `demo-traps.sh` | Plant each trap in the demo and watch the guard catch it. |

## Quick start

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+ with pnpm 9 (`corepack enable`), and a
Postgres you can create databases in (`PGHOST`, `PGPORT`, `PGUSER`).

```bash
scripts/local-ci.sh --parallel                          # backend: build DB, guard, split, 4 shards, gate
scripts/demo-traps.sh                                   # plant four traps, watch each one get caught
cd frontend && pnpm install && pnpm build               # build once
pnpm test:unit && pnpm test:e2e:mock                    # Vitest, then the Playwright fast lane
```

`pnpm exec playwright install chromium` first if you have never run Playwright.

## Configuration reference

All options live in `fast-ci.toml`. The shipped file is a worked example for
Acme HR, a fictional company. Unknown keys are an error, so a typo cannot fall
back to a default silently.

### `[backend]`

| Key | Default | Meaning |
|---|---|---|
| `root` | `"backend"` | Directory the tests run from. |
| `tests` | `["tests"]` | Test roots, for the collection guard. |
| `python_files` | `["test_*.py"]` | pytest's `python_files` patterns. The guard explains a miss with them. |
| `collection_ignore` | `[]` | Globs of files that may define test-like functions but are not test modules. |
| `shards` | `4` | Parallel test jobs. Wall clock ≈ total test time / shards + per-job setup. |
| `group_by` | `"test"` | `"test"` balances best. `"file"` keeps files together; one slow file then decides the wall clock. |
| `reruns` | `0` | Retries per failing test (pytest-rerunfailures). |
| `rerun_policy` | `"fail"` | A test that passes only on retry: `fail` the run, `warn` loudly, or `allow`. |
| `durations_artifact` | `"backend-test-durations"` | Artifact the gate publishes on every run; the split reads the latest one from `main`. |
| `durations_file` | `".test_durations.json"` | Committed fallback when no artifact exists yet. |
| `migration_inputs` | `["migrations/**"]` | Everything that shapes the test schema. Hashed into the cache key and stamped into the dump. |
| `migrate_command` | `""` | Command that migrates `$DATABASE_URL`. |
| `postgres_image`, `postgres_major` | `postgres:17`, `17` | Service image; the major version is part of the cache key. |
| `paths` | `["**"]` | Changes under these paths make the backend jobs run on a pull request. |

### `[frontend]`

| Key | Default | Meaning |
|---|---|---|
| `root` | `"frontend"` | App directory. |
| `vitest_shards`, `playwright_shards` | `2`, `2` | Matrix sizes. |
| `browsers` | `["chromium"]` | Browsers to install and cache. |
| `playwright_retries` | `0` | Playwright `retries`. |
| `fail_on_flaky` | `true` | Playwright `failOnFlakyTests`: a test that passes only on retry fails the run. |
| `paths` | `["**"]` | Path filter for pull requests. |
| `lanes.<event>` | see below | Which Playwright lanes run for each trigger: `mock`, `full`, or both. |

Default lanes: `pull_request = ["mock"]`, `push = ["mock", "full"]`,
`schedule = ["mock", "full"]`, `workflow_dispatch = ["mock", "full"]`. A
manual run can override them from the Actions tab.

### Adopting it in your repository

1. Copy `scripts/`, `.github/actions/` and the two workflows; copy
   `fast-ci.toml` and change `root`, `migration_inputs`, `migrate_command`
   and the paths.
2. Load the plugin in your root `conftest.py`: put `scripts/` on `sys.path`
   and add `pytest_plugins = ["pytest_honest"]`.
3. Make your test database fixture copy the template
   (`CREATE DATABASE <name> TEMPLATE <base>`); see `backend/tests/conftest.py`.
4. Point the full Playwright lane at your real backend instead of
   `frontend/server/demo-api.mjs`.
5. In branch protection, require only `CI result` from each workflow.

## How it was used in practice

The patterns here were first built for an HR and payroll SaaS in the Gulf,
with a Django and Postgres backend and a Next.js frontend tested with
Playwright. This repository is a from-scratch, generic rebuild of them.

- **Backend CI went from about 20 minutes to 8 shards of 3 to 4 minutes
  each.** The migrated database was restored from a cache instead of being
  rebuilt in every job, and shards were balanced on recorded durations. Before
  that, a count-based split left the slowest shard several times longer than
  the fastest.
- **The frontend Playwright gate went from 42-45 minutes to about 16.** The
  app was built once, the browser suite was sharded with one merged report,
  and pull requests ran the mocked-API lane while the full end-to-end suite
  moved to merges and nightly runs.
- **CI became honest.** Retries that had been hiding failures were exposed,
  so a failure showed up as a failure. Test files that had never run were
  found and brought back into the suite. The new,
  balanced split also surfaced tests that only passed in a particular order,
  and those were made independent.

The effect on the team was less about minutes than about trust: a red run
meant something was wrong, and a green run meant it was safe to merge.

## Proof, on this repository

Local demo numbers, from one machine. They show the mechanisms working; the
absolute times are small because the demo is small. Real suites are where the
savings are measured in minutes.

Backend, 390 tests, four shards run as separate processes:

| Split | Slowest shard |
|---|---:|
| No sharding | 5.3 s |
| By file | 4.8 s (one bulk-payroll file is 4.5 s on its own) |
| By test count | 2.3 s |
| By recorded duration | 1.7 s; all four shards in parallel: 1.9 s |

Test database: migrate-and-dump ~0.4 s, restore from the dump ~0.1 s, copy
from the template for each test process ~25 ms.

Playwright mock lane, 26 specs, 2 workers: 3.4 s unsharded, 2.4 s for the
slowest of three shards (mostly browser and server start-up). Vitest's 223
tests take a fifth of a second, so sharding them here only demonstrates the
wiring.

The guards, from `scripts/demo-traps.sh`:

```
== 1. A test file with the wrong name
::error title=Test never runs::tests/unit/leave_days_checks.py: defines tests but its name does not match test_*.py
== 2. A whole module skipped by a missing optional import
::error title=Test never runs::tests/unit/test_export_optional.py: the whole module was skipped (...)
== 3. A flaky test retried into green
59 passed, 1 rerun in 0.03s
  -> as expected (exit 0): pytest alone reports green
::error title=Honest CI gate::passed only after 1 retry(ies): tests/unit/test_flaky_demo.py::test_payslip_pdf_renders
== 4. A cached database dump that no longer matches the migrations
test-db: dump is stale: it holds fingerprint 'c59754441c7eafddf0a4', the code expects '7ff635d51cf4be6ef1c6'
all four traps were caught
```

## License

MIT. See [LICENSE](LICENSE).
