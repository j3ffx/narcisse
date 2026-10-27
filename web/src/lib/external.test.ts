import { describe, expect, it } from 'vitest';
import { leavesNarcisse } from './external';

const ORIGIN = 'http://narcisse.localhost';

describe('leavesNarcisse', () => {
  it('names a page outside Narcisse', () => {
    expect(leavesNarcisse('https://video.example.com/watch?v=1', ORIGIN)).toBe(
      'https://video.example.com/watch?v=1',
    );
    expect(leavesNarcisse('http://127.0.0.1:8888', ORIGIN)).toBe('http://127.0.0.1:8888/');
  });

  it('leaves Narcisse’s own pages and mailto: links alone', () => {
    expect(leavesNarcisse('/profils/1', ORIGIN)).toBeNull();
    expect(leavesNarcisse(`${ORIGIN}/scans/2`, ORIGIN)).toBeNull();
    expect(leavesNarcisse('mailto:info@example.org', ORIGIN)).toBeNull();
  });
});
