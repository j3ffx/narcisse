/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

// The API runs on uvicorn (scripts/dev.mjs); in production the Python package serves this build.
const API = `http://127.0.0.1:${process.env.NARCISSE_PORT ?? 8765}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { port: 5173, strictPort: true, proxy: { '/api': API } },
  build: {
    outDir: fileURLToPath(new URL('../src/narcisse/web/static', import.meta.url)),
    emptyOutDir: true,
    // Served from the user's own disk, never over a network: one bundle loads fastest.
    chunkSizeWarningLimit: 1000,
  },
  test: { include: ['src/**/*.test.ts'] },
});
