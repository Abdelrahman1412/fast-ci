#!/usr/bin/env node
// Compare a merged Playwright JSON report with what should have run.
//
//   node check-playwright-run.mjs --report merged.json --listed listed.json --projects mock,full
//
// Fails when fewer tests ran than were listed for the active projects (a shard
// died, a project was skipped), when any test failed, or when one was flaky.
import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const opt = (name) => args[args.indexOf(`--${name}`) + 1];
const report = JSON.parse(readFileSync(opt('report'), 'utf8'));
const listed = JSON.parse(readFileSync(opt('listed'), 'utf8'));
const projects = opt('projects').split(',').filter(Boolean);

const expected = projects.reduce((sum, p) => sum + (listed.byProject[p] ?? 0), 0);
const s = report.stats;
const ran = s.expected + s.unexpected + s.flaky + s.skipped;
const lines = [
  `listed for ${projects.join('+')}: ${expected}`,
  `ran: ${ran} (passed ${s.expected}, failed ${s.unexpected}, flaky ${s.flaky}, skipped ${s.skipped})`,
];
const problems = [];
if (ran !== expected) problems.push(`${expected - ran} listed test(s) never ran`);
if (s.unexpected) problems.push(`${s.unexpected} test(s) failed`);
if (s.flaky) problems.push(`${s.flaky} test(s) passed only on retry`);
console.log(lines.join('\n'));
for (const p of problems) console.log(`::error title=Playwright run::${p}`);
process.exit(problems.length ? 1 : 0);
