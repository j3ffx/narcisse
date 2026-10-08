#!/usr/bin/env node
// Commit times are personal data (they show when someone works). Every commit
// is therefore dated at noon UTC of its day: only the day is kept.
//   node scripts/commit-date.mjs          post-commit hook: re-dates HEAD if needed
//   node scripts/commit-date.mjs --check  lists unpushed commits that are not re-dated (exit 1)
//   node scripts/commit-date.mjs --fix    re-dates every unpushed commit (rewrites them)
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const git = (args, env = {}) =>
  execFileSync('git', args, { encoding: 'utf8', env: { ...process.env, ...env } }).trim();

/** "2026-10-06T12:00:00+0000" for a commit timestamp in seconds. */
export function noonOf(epochSeconds) {
  return `${new Date(epochSeconds * 1000).toISOString().slice(0, 10)}T12:00:00+0000`;
}

/** True when both dates of the commit are at 12:00:00 +0000. */
export function isNormalized(authorIso, committerIso) {
  return [authorIso, committerIso].every((iso) => / 12:00:00 \+0000$/.test(iso));
}

function unpushed() {
  const out = git(['log', '--format=%H %ct|%ai|%ci', '--branches', '--not', '--remotes']);
  return out
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [head = '', ai = '', ci = ''] = line.split('|');
      const [sha = '', ct = '0'] = head.split(' ');
      return { sha, ct: Number(ct), ai, ci };
    });
}

function main(argv) {
  if (argv[0] === '--check') {
    const bad = unpushed().filter((c) => !isNormalized(c.ai, c.ci));
    for (const c of bad)
      console.error(`✖ ${c.sha.slice(0, 7)} is dated ${c.ci} (run: npm run fix:dates)`);
    return bad.length ? 1 : 0;
  }

  if (argv[0] === '--fix') {
    const commits = unpushed();
    if (!commits.length) return 0;
    const oldest = commits.at(-1)?.sha;
    const base = git(['rev-list', '--parents', '-n', '1', oldest ?? 'HEAD']).split(' ')[1];
    // In --env-filter, GIT_COMMITTER_DATE reads "@<seconds> <offset>".
    const script =
      'ts=${GIT_COMMITTER_DATE#@}; ts=${ts%% *}; ' +
      'd="$(date -u -d "@$ts" +%Y-%m-%d)T12:00:00+0000"; ' +
      'export GIT_AUTHOR_DATE="$d" GIT_COMMITTER_DATE="$d"';
    git(['filter-branch', '-f', '--env-filter', script, base ? `${base}..HEAD` : 'HEAD'], {
      FILTER_BRANCH_SQUELCH_WARNING: '1',
    });
    console.log(`${commits.length} commit(s) re-dated at noon UTC`);
    return 0;
  }

  // post-commit hook. Never amend in the middle of a rebase, merge or cherry-pick:
  // the pre-push check catches those commits and `--fix` re-dates them afterwards.
  const gitDir = git(['rev-parse', '--git-dir']);
  const busy = ['rebase-merge', 'rebase-apply', 'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD'];
  if (busy.some((name) => existsSync(join(gitDir, name)))) return 0;
  const [ct = '0', ai = '', ci = ''] = git(['log', '-1', '--format=%ct|%ai|%ci']).split('|');
  if (isNormalized(ai, ci)) return 0;
  const date = noonOf(Number(ct));
  git(['commit', '--amend', '--no-edit', '--no-verify', '--allow-empty', `--date=${date}`], {
    GIT_COMMITTER_DATE: date,
  });
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  process.exitCode = main(process.argv.slice(2));
