import { describe, expect, it } from 'vitest';
import { sha1, sha1Hex } from './sha1';

const hex = (bytes: Uint8Array) => [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');

describe('sha1', () => {
  it('matches the standard test vectors', () => {
    const encode = (text: string) => new TextEncoder().encode(text);
    expect(hex(sha1(encode('')))).toBe('da39a3ee5e6b4b0d3255bfef95601890afd80709');
    expect(hex(sha1(encode('abc')))).toBe('a9993e364706816aba3e25717850c26c9cd0d89d');
    expect(hex(sha1(encode('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq')))).toBe(
      '84983e441c3bd26ebaae4aa1f95129e5e54670f1',
    );
    expect(hex(sha1(encode('a'.repeat(1000))))).toBe('291e9a6c66994949b57ba5e650361e98fc36b1ba');
  });

  it('gives the hash Pwned Passwords knows, in upper case', async () => {
    // « password », the most leaked of all.
    expect(await sha1Hex('password')).toBe('5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8');
    expect(hex(sha1(new TextEncoder().encode('password'))).toUpperCase()).toBe(
      '5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8',
    );
  });
});
