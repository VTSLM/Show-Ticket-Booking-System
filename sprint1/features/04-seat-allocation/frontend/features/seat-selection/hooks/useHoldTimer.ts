import { useState, useEffect, useRef } from 'react';
import { calculateRemainingSeconds, formatCountdown } from '../utils/clockOffset';

interface UseHoldTimerOptions {
  expiresAt: string | null;
  clockOffsetMs: number;
  onExpire?: () => void;
}

export function useHoldTimer({
  expiresAt,
  clockOffsetMs,
  onExpire,
}: UseHoldTimerOptions) {
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    if (!expiresAt) {
      setSecondsLeft(0);
      return;
    }

    const updateTimer = () => {
      const remaining = calculateRemainingSeconds(expiresAt, clockOffsetMs);
      setSecondsLeft(remaining);

      if (remaining <= 0) {
        if (onExpireRef.current) {
          onExpireRef.current();
        }
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);

    return () => clearInterval(interval);
  }, [expiresAt, clockOffsetMs]);

  return {
    secondsLeft,
    formattedTime: formatCountdown(secondsLeft),
    isCritical: secondsLeft > 0 && secondsLeft <= 60,
    isExpired: secondsLeft <= 0 && !!expiresAt,
  };
}
