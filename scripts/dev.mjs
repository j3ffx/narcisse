#!/usr/bin/env node
// `npm run dev`: the API (uvicorn, reloading on Python changes) and the UI (Vite, hot reload),
// in demo mode, with data kept apart from real profiles (narcisse-dev in the OS data directory).
import { spawn } from 'node:child_process';

const port = process.env.NARCISSE_PORT ?? '8765';
const env = {
  ...process.env,
  NARCISSE_DEV: '1',
  NARCISSE_DEMO: process.env.NARCISSE_DEMO ?? '1',
  NARCISSE_PORT: port,
  NARCISSE_DEV_ORIGINS: 'http://localhost:5173',
};
const run = (command, args) =>
  spawn(command, args, { env, stdio: 'inherit', shell: process.platform === 'win32' });

const children = [
  run('uv', [
    'run',
    'uvicorn',
    'narcisse.app:app_from_env',
    '--factory',
    '--reload',
    '--reload-dir',
    'src',
    '--host',
    '127.0.0.1',
    '--port',
    port,
  ]),
  run('npm', ['run', 'dev', '-w', 'web']),
];

const stop = () => children.forEach((child) => child.kill());
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
for (const child of children) child.on('exit', (code) => code && stop());
console.log('\nNarcisse (développement) : http://localhost:5173\n');
