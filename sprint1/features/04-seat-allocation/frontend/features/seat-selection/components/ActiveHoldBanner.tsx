import React from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, XCircle } from 'lucide-react';
import { useSeatSelection } from '../context/SeatSelectionContext';
import { HoldCountdown } from './HoldCountdown';

export const ActiveHoldBanner: React.FC = () => {
  const router = useRouter();
  const { state, releaseCurrentHold, handleHoldExpired } = useSeatSelection();

  if (!state.myHold) return null;

  const handleContinue = () => {
    const template = process.env.NEXT_PUBLIC_CHECKOUT_PATH_TEMPLATE || '/checkout/{bookingId}';
    const checkoutUrl = template.replace('{bookingId}', state.myHold!.booking_id);
    router.push(checkoutUrl);
  };

  return (
    <div
      role="alert"
      className="w-full bg-gradient-to-r from-amber-950/80 via-surface-card to-amber-950/80 border border-amber-500/40 rounded-xl p-4 mb-6 shadow-xl backdrop-blur-md"
    >
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 text-left">
          <div className="p-2 bg-amber-500/20 text-amber-400 rounded-lg flex-shrink-0">
            <AlertCircle className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">
              You have seats on hold (Booking #{state.myHold.booking_number})
            </h4>
            <p className="text-xs text-amber-200/80 mt-0.5">
              New seat selections are paused while this hold is active.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 flex-shrink-0">
          <HoldCountdown
            expiresAt={state.myHold.expires_at}
            clockOffsetMs={state.clockOffsetMs}
            onExpire={handleHoldExpired}
          />

          <button
            type="button"
            onClick={releaseCurrentHold}
            disabled={state.isSubmitting}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-gray-300 hover:text-white bg-surface-card hover:bg-gray-800 border border-gray-700 rounded-lg transition-colors duration-150 disabled:opacity-50"
          >
            <XCircle className="w-4 h-4 text-gray-400" />
            <span>Release</span>
          </button>

          <button
            type="button"
            onClick={handleContinue}
            className="inline-flex items-center space-x-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-md transition-colors duration-150"
          >
            <span>Continue</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
