/** Headless Chrome draws WebGL in software unless told to use the GPU: these flags ask for it. */
export const GPU = [
  '--ignore-gpu-blocklist',
  '--enable-gpu',
  ...(process.platform === 'win32' ? ['--use-angle=d3d11'] : []),
];
