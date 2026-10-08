#!/usr/bin/env node
// Runs on `npm install` (prepare): enables the versioned git hooks of
// .githooks/ (pre-push privacy check). Silent no-op outside a git checkout,
// e.g. on the Cloudflare Pages build machine.
import { execFileSync } from 'node:child_process';

try {
  execFileSync('git', ['rev-parse', '--is-inside-work-tree'], { stdio: 'ignore' });
  execFileSync('git', ['config', 'core.hooksPath', '.githooks'], { stdio: 'ignore' });
} catch {
  // Not a git checkout: nothing to do.
}
