import React from 'react';
import clsx from 'clsx';
import { Clock } from 'lucide-react';
import { useHoldTimer } from '../hooks/useHoldTimer';

interface HoldCountdownProps {
  expiresAt: string | null;
  clockOffsetMs: number;
  onExpire?: () => void;
  className?: string;
}

export const HoldCountdown: React.FC<HoldCountdownProps> = ({
  expiresAt,
  clockOffsetMs,
  onExpire,
  className,
}) => {
  const { formattedTime, isCritical, isExpired } = useHoldTimer({
    expiresAt,
    clockOffsetMs,
    onExpire,
  });

  if (!expiresAt) return null;

  return (
    <div
      role="timer"
      aria-live="polite"
      className={clsx(
        'inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg border font-mono text-sm font-semibold transition-colors duration-200',
        isCritical && 'border-red-500/80 bg-red-950/60 text-red-300 animate-pulse',
        !isCritical && !isExpired && 'border-amber-500/50 bg-amber-950/40 text-amber-300',
        isExpired && 'border-gray-700 bg-gray-900 text-gray-500',
        className
      )}
    >
      <Clock className={clsx('w-4 h-4', isCritical ? 'text-red-400' : 'text-amber-400')} />
      <span>{isExpired ? '00:00' : formattedTime}</span>
    </div>
  );
};
