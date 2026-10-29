/**
 * Computes difference between server clock and client laptop clock.
 * offsetMs = server_time - client_time.
 * A positive offset means the server clock is ahead of client clock.
 */
export function computeClockOffset(serverTimeIso: string, clientNowMs?: number): number {
  try {
    const serverMs = Date.parse(serverTimeIso);
    if (isNaN(serverMs)) return 0;
    const clientMs = clientNowMs ?? Date.now();
    return serverMs - clientMs;
  } catch (e) {
    return 0;
  }
}

/**
 * Derives accurate remaining countdown seconds against server expires_at,
 * neutralising client system clock skew.
 */
export function calculateRemainingSeconds(
  expiresAtIso: string,
  clockOffsetMs: number,
  clientNowMs?: number
): number {
  try {
    const expiresMs = Date.parse(expiresAtIso);
    if (isNaN(expiresMs)) return 0;
    const clientMs = clientNowMs ?? Date.now();
    const serverAdjustedNowMs = clientMs + clockOffsetMs;
    const diffMs = expiresMs - serverAdjustedNowMs;
    return Math.max(0, Math.floor(diffMs / 1000));
  } catch (e) {
    return 0;
  }
}

/**
 * Formats countdown seconds to mm:ss string.
 */
export function formatCountdown(seconds: number): string {
  const safeSec = Math.max(0, Math.floor(seconds));
  const m = Math.floor(safeSec / 60);
  const s = safeSec % 60;
  const mm = m < 10 ? `0${m}` : `${m}`;
  const ss = s < 10 ? `0${s}` : `${s}`;
  return `${mm}:${ss}`;
}
