import { describe, it, expect } from 'vitest';
import {
  computeClockOffset,
  calculateRemainingSeconds,
  formatCountdown,
} from '../features/seat-selection/utils/clockOffset';

describe('clockOffset', () => {
  it('computes offset between server time and local system clock', () => {
    // Client clock is 10:00:00, server clock is 10:00:05 (server is 5000ms ahead)
    const clientTimeMs = 1700000000000;
    const serverTimeIso = new Date(clientTimeMs + 5000).toISOString();

    const offset = computeClockOffset(serverTimeIso, clientTimeMs);
    expect(offset).toBe(5000);
  });

  it('calculates countdown accurately despite skewed local client clock', () => {
    // Client clock is running 2 minutes slow (-120000ms)
    // Server says lock expires at 1700000300000 (5 minutes from server now)
    const serverNowMs = 1700000000000;
    const clientNowMs = serverNowMs - 120000;
    const expiresAtIso = new Date(serverNowMs + 300000).toISOString(); // 300 seconds left

    const offsetMs = computeClockOffset(new Date(serverNowMs).toISOString(), clientNowMs);
    expect(offsetMs).toBe(120000);

    const remainingSec = calculateRemainingSeconds(expiresAtIso, offsetMs, clientNowMs);
    expect(remainingSec).toBe(300);
  });

  it('clamps remaining seconds to zero once past expiration', () => {
    const serverNowMs = 1700000000000;
    const expiresAtIso = new Date(serverNowMs - 5000).toISOString(); // Expired 5 seconds ago
    const remainingSec = calculateRemainingSeconds(expiresAtIso, 0, serverNowMs);
    expect(remainingSec).toBe(0);
  });

  it('formats remaining seconds to mm:ss format', () => {
    expect(formatCountdown(300)).toBe('05:00');
    expect(formatCountdown(59)).toBe('00:59');
    expect(formatCountdown(5)).toBe('00:05');
    expect(formatCountdown(0)).toBe('00:00');
  });
});
