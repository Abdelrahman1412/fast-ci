# The fast-CI playbook

How to make a slow CI fast without making it lie. Each technique says when it
helps, when it does not, and what it costs. The traps at the end are the ones
that turn a fast pipeline into a green light that means nothing.

## 1. Profile before you change anything

Guessing is how teams add shards to a pipeline whose real cost is a 6-minute
dependency install. Measure first.

```bash
scripts/ci-timings.py --repo OWNER/REPO --workflow backend.yml --runs 20
scripts/ci-timings.py --repo OWNER/REPO --workflow backend.yml --runs 20 --event pull_request --steps 20
```

It prints the run wall clock (median and p90), each job's duration, the spread
between the fastest and slowest shard of a matrix job, queue wait, and the
slowest steps across all jobs. Read it in this order:

1. **Wall clock vs. the longest job.** If the run takes 25 minutes and the
   longest job 12, the time is in the dependency chain or in queueing, not in
   the tests. Look at `needs:` before you look at pytest.
2. **Queue wait.** Minutes of waiting mean you are out of runners. More shards
   will make it worse.
3. **Slowest steps.** Sort out setup first: install, browser download, build,
   database migrations. They are usually cheaper to fix than the tests and
   they repeat in every shard.
4. **Shard spread.** A spread of more than ~20% of the median shard means the
   split is unbalanced. Fix the split before adding shards.

Then write down the target: "PR feedback under 10 minutes at p90" is a goal;
"faster" is not.

## 2. Techniques

### Cache dependencies (uv, pip, pnpm)

- **Helps:** always, as long as the key is the lockfile. `setup-uv` with
  `cache-dependency-glob: backend/uv.lock`; `setup-node` with `cache: pnpm`.
- **Does not help:** when the install is already fast, or when the cache is
  bigger than what it saves (a 3 GB cache restore can take longer than a
  clean install from a nearby mirror).
- **Cost:** none if keyed right. Keyed wrong, it is the first trap below.

### Build once, test many

Build the app in one job and hand the output to every test shard as an
artifact (`web-dist` in `frontend.yml`). Each shard then only installs, starts
a static server and runs.

- **Helps:** when the build takes more than a minute and there are several
  test jobs. A 4-minute build in 6 shards is 20 wasted runner-minutes per run,
  and 4 minutes of wall clock that a shard cannot start without.
- **Does not help:** when the build is seconds long (this demo's is), or when
  shards need different builds.
- **Cost:** an upload/download step and an artifact to keep consistent with
  the code. Build from the same commit, in the same run, always.

### Migrated test-database cache

Running every migration from zero in every shard is the classic backend CI
tax. Instead (`.github/actions/test-db`, `scripts/test_db.sh`):

1. One job migrates a fresh database and dumps it (`pg_dump -Fc`).
2. The dump is cached under a key that is a hash of **every** input that
   shapes the schema: migration files, the code that applies them, and the
   Postgres major version (`scripts/fingerprint.py`).
3. The same hash is written into the dump itself. A restore checks it, so a
   dump that does not match the code is refused and rebuilt, whatever the
   cache served.
4. Each shard restores the dump once, and each test process copies it with
   `CREATE DATABASE ... TEMPLATE`, which takes milliseconds.
5. A run on `main` warms the cache. Caches written on a pull request are only
   visible to that pull request; caches on the default branch are visible to
   all of them.

- **Helps:** when migrations take more than ~30 seconds, or when there are
  many shards. The saving multiplies by the shard count.
- **Does not help:** with a handful of fast migrations; the restore is not
  free either. In this demo, migrate-and-dump takes ~0.4 s and restore ~0.1 s:
  the mechanism is proven, the saving is small. Real schemas with years of
  migrations and reference data are where it pays.
- **Cost:** one more job on the critical path when the cache misses. Keep a
  `timeout-minutes` on it (see the DB-build trap).

### Duration-balanced sharding

Wall clock is the **slowest** shard plus setup. Splitting by test count or by
file assumes all tests cost the same; they never do. `scripts/split_tests.py`
splits by recorded duration, longest first onto the least-loaded shard:

- durations come from the last successful run on `main` (an artifact the
  gate job publishes), with a committed file as a fallback;
- tests without a recorded duration get the median, so a stale file costs
  balance, never correctness;
- the shard files are pytest argument files (`pytest @shard-3.txt`), so the
  shards run exactly the tests the plan assigned, and the gate can prove it.

Local demo numbers (one laptop, four shards run as separate processes, the
same 390 tests):

| split | slowest shard |
|---|---:|
| no sharding | 5.3 s |
| by file | 4.8 s |
| by test count | 2.3 s |
| by recorded duration | 1.7 s |

- **Helps:** suites over a few minutes, where the per-shard setup (checkout,
  install, database restore) is small next to the test time.
- **Does not help:** past the point where setup dominates. Each shard pays it
  again. If setup is 90 seconds and tests are 3 minutes, going from 4 to 8
  shards saves about 20 seconds of wall clock and doubles the runner bill.
  Rule of thumb: wall clock is roughly `total_test_time / shards + setup`.
- **Cost:** order-dependent tests show up. A new split puts tests next to
  neighbours they have never met, and hidden coupling (shared rows, a cache
  never cleared, a module-level counter) fails. That is a finding, not noise:
  fix the coupling, do not pin the split.

### Fast lane and full lane (Playwright)

Not every check has to block every pull request. `fast-ci.toml` maps each
trigger to lanes:

```toml
[frontend.lanes]
pull_request = ["mock"]          # every API call stubbed in the browser
push = ["mock", "full"]          # merges to main
schedule = ["mock", "full"]      # nightly
```

The mock lane needs no backend, no database and no seed data, so it is fast
and almost never flaky. An unmocked call fails the test instead of hitting a
network that is not there. The full lane runs against a real API.

- **Helps:** when the end-to-end stack is slow or fragile to stand up, and
  most regressions are in the UI layer.
- **Does not help:** if nobody looks at the nightly result. A full lane that
  only runs at night needs an owner and an alert, or it rots.
- **Cost:** mocks drift from the real API. Keep the mock data typed against
  the same types the app uses, and keep the full lane running somewhere.

### Playwright sharding with merged reports

`--shard=i/n` across matrix jobs, each writing a blob report; one job merges
them (`playwright merge-reports`) into a single HTML report, and checks that
the shards together ran every listed test (`scripts/check-playwright-run.mjs`).

- **Helps:** suites of more than a few minutes. Browser start-up and the web
  server cost each shard a fixed 10-30 seconds.
- **Does not help:** small suites. In this demo, 26 specs take 3.4 s
  unsharded and 2.4 s for the slowest of three shards: most of that is
  start-up.
- **Cost:** a cached browser install (`~/.cache/ms-playwright`, keyed on the
  lockfile, which pins the Playwright version). The cache holds the browser
  but not its system libraries: on a hit, still run `playwright install-deps`.

### Concurrency: cancel superseded runs

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

- **Helps:** busy pull requests. Three quick pushes cost one run, not three.
- **Does not help:** on `main`. Never cancel there: every merge needs a
  complete result, and runs on `main` are what warm the caches.

### Path filters, done so they do not block merges

A workflow-level `paths:` filter means the workflow does not start at all, so
a required check from it stays "Expected - waiting" forever and the pull
request cannot merge. Instead, always start the workflow, decide in a cheap
`plan` job (`dorny/paths-filter`), and skip the expensive jobs.

### One aggregate "CI result" job

Branch protection requires one check, `CI result`, which runs with
`if: always()` and judges every other job (`scripts/ci_result.py`). Adding or
renaming a shard never touches branch protection again.

## 3. The traps

### Caches keyed wrongly serve stale data

- **Symptom:** tests pass in CI and fail locally, or the reverse; a migration
  "isn't applied" in CI; a fix does not take effect until someone clears the
  cache by hand.
- **Causes:** the key misses an input (migrations only, not the code that
  applies them; not the Postgres major); `restore-keys` falls back to an older
  entry, and nothing checks what came back; the key is built from a glob that
  matches no files, so it never changes.
- **Guard:** put every input in the key, and verify the restored content, not
  just the cache hit. Here the fingerprint is stamped inside the dump and
  checked on restore. `scripts/demo-traps.sh` step 4 shows a stale dump being
  refused. Avoid `restore-keys` for anything that must match exactly.

### One slow file dominates a shard

- **Symptom:** shard spread is large and stable. Adding shards does not move
  the wall clock.
- **Cause:** splitting by file (or by class with heavy shared fixtures) when
  one file holds most of the time. In the demo, `test_payroll_run_bulk.py`
  is 4.5 s of a 5.1 s suite; split by file, its shard decides everything.
- **Guard:** split by test (`group_by = "test"`). The splitter prints a
  warning when any one unit is longer than an even shard. If a file must stay
  together, split the file.

### A skipped job reads as success

- **Symptom:** a broken pull request merges. Its tests "passed".
- **Cause:** GitHub counts a skipped job as passing a required check. When a
  job's dependency fails, the job is skipped, so requiring only the last job
  in the chain lets the failure through. Requiring every matrix shard by name
  breaks the day the shard count changes.
- **Guard:** one required `CI result` job with `if: always()` that fails on
  any failure, any cancellation, and any skip the plan did not intend
  (`--may-skip` lists the intended ones).

### Retries mask failures

- **Symptom:** the suite is "green" and the product is broken one time in
  five. Nobody can say which tests are flaky.
- **Cause:** retries (`--reruns`, Playwright `retries`) turn a failing first
  attempt into a pass. The report shows one quiet "R".
- **Guard:** keep a retry if you want the diagnostic (a test that passes on
  retry is flaky, one that fails twice is broken), but decide what flaky
  means. `rerun_policy = "fail"` fails the run and names the test;
  `"warn"` lets it pass with a loud annotation while you clean up. For
  Playwright, `failOnFlakyTests`. `scripts/demo-traps.sh` step 3 shows pytest
  exiting 0 for a flaky test and the gate failing it.
- **Also:** record durations from runs without retries, or the retry's time
  pollutes the split.

### Tests that never run

- **Symptom:** coverage of a feature is "there" and catches nothing.
- **Causes:** a file named `employees_test.py` when only `test_*.py` is
  collected; an import error hidden by `--continue-on-collection-errors` or a
  `try/except ImportError: pytest.skip(...)`; a module-level `importorskip`; a
  spec outside every Playwright project's `testDir`; a stray `test.only`.
- **Guard:** `scripts/check_collection.py` reads every file under the test
  roots that defines tests (with `ast`, nothing imported) and fails on any
  file pytest did not collect from, naming the reason.
  `scripts/check-specs.mjs` does the same for Playwright. `--strict-markers`,
  `--strict-config`, `xfail_strict` and `forbidOnly` close the smaller holes.
  After the shards run, the gate checks that their union is exactly the
  collected set: nothing lost by the split, nothing run twice.

### Database builds that time out

- **Symptom:** every shard hits its timeout at once, after 30 minutes of
  nothing, on the day someone adds a heavy data migration.
- **Cause:** on a cache miss, each shard migrates from scratch, in parallel,
  with the default job timeout of 6 hours or a generous shard timeout.
- **Guard:** build the database in one job with a tight `timeout-minutes`
  (it fails fast and by name), and make shards depend on it so they restore
  instead of rebuilding. In CI, `FASTCI_REQUIRE_TEMPLATE=1` makes a missing
  template an immediate error instead of a silent rebuild. Keep the
  Postgres image identical in the job that builds the dump and the jobs that
  restore it, and dump with client tools that match the server (here,
  `pg_dump` runs inside the service container).

## 4. A checklist for a new repository

1. Run `ci-timings.py` on the last 20 runs and write down the p90 target.
2. Fix setup first: lockfile-keyed caches, build once.
3. Add the database template cache if migrations take more than ~30 seconds.
4. Add the collection guard and the honest gate **before** sharding, so the
   split cannot lose tests silently.
5. Shard by duration. Start with `total_test_time / target`, then tune with
   the measured spread.
6. Put `CI result` in branch protection and remove every other required
   check.
7. Re-run `ci-timings.py` a week later. Keep the before/after in the pull
   request that made the change.
