/**
 * useCountdown.js
 * ===============
 * Phase 4 — countdown timer tied to the backend lock's expiresAt timestamp.
 *
 * Design decisions:
 * - Uses server-issued expiresAt, NOT a client-side start time + duration.
 *   This prevents drift if the user's tab goes to background.
 * - The confirm step (Phase 5) still re-verifies server-side — the timer
 *   is purely UI feedback.
 * - Cleans up the interval on unmount.
 */

import { useEffect, useRef, useState } from 'react';

export function useCountdown(expiresAt) {
  const [secondsLeft, setSecondsLeft] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!expiresAt) {
      setSecondsLeft(null);
      return;
    }

    const expiry = new Date(expiresAt).getTime();

    const tick = () => {
      const now = Date.now();
      const remaining = Math.max(0, Math.floor((expiry - now) / 1000));
      setSecondsLeft(remaining);
      if (remaining <= 0) {
        clearInterval(intervalRef.current);
      }
    };

    tick(); // immediate first tick
    intervalRef.current = setInterval(tick, 1000);

    return () => clearInterval(intervalRef.current);
  }, [expiresAt]);

  // Format mm:ss
  const formatted = secondsLeft !== null
    ? `${String(Math.floor(secondsLeft / 60)).padStart(2, '0')}:${String(secondsLeft % 60).padStart(2, '0')}`
    : null;

  const isExpired = secondsLeft === 0;
  const isWarning = secondsLeft !== null && secondsLeft <= 60;

  return { secondsLeft, formatted, isExpired, isWarning };
}
