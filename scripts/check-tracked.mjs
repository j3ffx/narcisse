#!/usr/bin/env node
// Guards the public repository against leaking private files or data.
// Runs in the pre-push hook (.githooks/pre-push) and in CI.
//
// Checks:
//  1. no forbidden file is tracked (local notes, .env files, local deny-list, databases);
//  2. no tracked file matches a .gitignore rule;
//  3. every commit author/committer uses a noreply e-mail address;
//  4. if a local, ignored `.private-patterns` file exists (one regex per line),
//     no tracked file content and no commit message matches any of them.
//     That file is never versioned, so the patterns themselves stay private.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';

const git = (...args) =>
  execFileSync('git', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });

const errors = [];

const FORBIDDEN = [
  /(^|\/)\.claude\//,
  /(^|\/)\.env(\..+)?$/,
  /(^|\/)\.private-patterns$/,
  /\.(db|sqlite3?)(-journal|-wal|-shm)?$/,
];
const ALLOWED = [/(^|\/)\.env\.example$/];

const tracked = git('ls-files', '-z').split('\0').filter(Boolean);

for (const file of tracked) {
  if (FORBIDDEN.some((re) => re.test(file)) && !ALLOWED.some((re) => re.test(file))) {
    errors.push(`forbidden file is tracked: ${file}`);
  }
}

const ignoredButTracked = git('ls-files', '-z', '-ci', '--exclude-standard')
  .split('\0')
  .filter(Boolean);
for (const file of ignoredButTracked) {
  errors.push(`tracked file matches .gitignore: ${file}`);
}

let hasCommits = true;
try {
  git('rev-parse', '--verify', '-q', 'HEAD');
} catch {
  hasCommits = false;
}

if (hasCommits) {
  const identities = new Set(git('log', '--all', '--format=%ae%n%ce').split('\n').filter(Boolean));
  for (const email of identities) {
    if (!/noreply/i.test(email)) {
      errors.push(`commit identity is not a noreply address: ${email}`);
    }
  }
}

if (existsSync('.private-patterns')) {
  const patterns = readFileSync('.private-patterns', 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .map((line) => new RegExp(line, 'i'));

  for (const file of tracked) {
    if (!existsSync(file)) continue;
    const content = readFileSync(file, 'utf8');
    for (const re of patterns) {
      if (re.test(content)) errors.push(`private pattern ${re} found in ${file}`);
    }
  }

  if (hasCommits) {
    const messages = git('log', '--all', '--format=%B');
    for (const re of patterns) {
      if (re.test(messages)) errors.push(`private pattern ${re} found in a commit message`);
    }
  }
}

if (errors.length > 0) {
  console.error('check-tracked: FAILED');
  for (const error of errors) console.error(`  - ${error}`);
  process.exit(1);
}

console.log(`check-tracked: OK (${tracked.length} tracked files)`);
