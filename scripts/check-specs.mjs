#!/usr/bin/env node
// Fail when a Playwright spec file exists but Playwright would never run it.
//
// - files that call test(...) but do not match the spec suffix (never picked up);
// - spec files outside every project's testDir (picked up by no project);
// - spec files whose tests were all filtered away.
//
// It asks Playwright itself (`playwright test --list --reporter=json`), so it
// sees exactly what a run would see.
//
//   node ../scripts/check-specs.mjs --dir e2e --suffix .spec.ts --ignore e2e/fixtures --out listed.json
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};
const dir = opt('dir', 'e2e');
const suffix = opt('suffix', '.spec.ts');
const ignore = (opt('ignore', '') || '').split(',').filter(Boolean);
const out = opt('out', '');

const walk = (path) =>
  statSync(path).isDirectory() ? readdirSync(path).flatMap((name) => walk(join(path, name))) : [path];

const callsTest = (file) => /(^|\n)\s*(test|it)(\.(only|skip|fixme|describe))?\s*\(/.test(readFileSync(file, 'utf8'));

const files = walk(dir)
  .map((f) => relative('.', f))
  .filter((f) => /\.(m?[jt]s)$/.test(f) && !ignore.some((prefix) => f.startsWith(prefix)));

const listing = JSON.parse(
  execFileSync('npx', ['playwright', 'test', '--list', '--reporter=json'], {
    encoding: 'utf8',
    env: { ...process.env, CI: '' },
    maxBuffer: 64 * 1024 * 1024,
  }),
);
const listedFiles = new Set();
let listedTests = 0;
const byProject = {};
const visit = (suite) => {
  for (const spec of suite.specs ?? []) {
    for (const t of spec.tests ?? []) {
      listedFiles.add(relative('.', resolve(listing.config.rootDir, spec.file)));
      listedTests += 1;
      byProject[t.projectName] = (byProject[t.projectName] ?? 0) + 1;
    }
  }
  for (const child of suite.suites ?? []) visit(child);
};
for (const suite of listing.suites ?? []) visit(suite);
for (const error of listing.errors ?? []) console.log(`::error title=Spec error::${error.message?.split('\n')[0]}`);

const problems = [];
for (const file of files) {
  const isSpec = file.endsWith(suffix);
  if (!isSpec && callsTest(file)) problems.push(`${file}: calls test() but does not end in ${suffix}, so it never runs`);
  if (isSpec && !listedFiles.has(file)) problems.push(`${file}: no project lists any test from it`);
}
if ((listing.errors ?? []).length) problems.push('Playwright reported errors while listing tests');

console.log(`spec guard: ${listedTests} tests from ${listedFiles.size} files (${JSON.stringify(byProject)})`);
if (out) writeFileSync(out, JSON.stringify({ total: listedTests, byProject }, null, 1) + '\n');
for (const p of problems) console.log(`::error title=Spec never runs::${p}`);
if (problems.length) {
  console.log(`spec guard: FAILED, ${problems.length} problem(s)`);
  process.exit(1);
}
console.log('spec guard: every spec file is listed');
