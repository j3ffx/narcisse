#!/usr/bin/env node
// Prints the CHANGELOG.md notes of one version, for its GitHub release.
//   node scripts/release-notes.mjs 0.1.0
// Fails when the version has no entry: every release must say what it brings.
import { readFileSync } from 'node:fs';

const version = process.argv[2]?.replace(/^v/, '');
if (!version) {
  console.error('usage: node scripts/release-notes.mjs <version>');
  process.exit(2);
}

const lines = readFileSync('CHANGELOG.md', 'utf8').replace(/\r\n/g, '\n').split('\n');
const start = lines.findIndex(
  (line) => line.startsWith(`## ${version} `) || line === `## ${version}`,
);
if (start === -1) {
  console.error(`CHANGELOG.md has no entry for ${version}`);
  process.exit(1);
}
const end = lines.findIndex((line, i) => i > start && line.startsWith('## '));
// The file wraps its sentences; GitHub would show each wrap as a line break.
const unwrapped = [];
for (const line of lines.slice(start + 1, end === -1 ? undefined : end)) {
  const previous = unwrapped.at(-1);
  const continues = line.trim() && !/^(- |#)/.test(line) && previous && !previous.startsWith('#');
  if (continues) unwrapped[unwrapped.length - 1] = `${previous} ${line.trim()}`;
  else unwrapped.push(line);
}
console.log(unwrapped.join('\n').trim());
