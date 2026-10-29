import React from 'react';
import clsx from 'clsx';
import { X, ArrowRight, ShieldCheck, UserCheck, AlertTriangle } from 'lucide-react';
import { useSeatSelection } from '../context/SeatSelectionContext';
import { formatCurrency, formatShowDateTime } from '../utils/formatters';

export const SummaryPanel: React.FC = () => {
  const {
    state,
    user,
    selectedSeats,
    subtotal,
    convenienceFee,
    totalPrice,
    removeSeat,
    proceedToCheckout,
  } = useSeatSelection();

  const show = state.mapData?.show;
  const isBookable = state.mapData?.bookable ?? true;
  const bookableReason = state.mapData?.bookable_reason;
  const maxSeats = state.mapData?.max_seats_per_booking ?? 8;
  const count = selectedSeats.length;

  const { timeStr } = show ? formatShowDateTime(show.start_time) : { timeStr: '' };

  const isButtonDisabled = !isBookable || count === 0 || state.isSubmitting || !!state.myHold;

  let buttonText = 'Proceed to checkout';
  let buttonReason = '';

  if (!isBookable) {
    buttonText = 'Booking Closed';
    buttonReason = bookableReason || 'Show is not bookable';
  } else if (state.myHold) {
    buttonText = 'Hold Active';
    buttonReason = 'Resolve active hold above to book new seats';
  } else if (!user) {
    buttonText = count > 0 ? 'Sign in to continue' : 'Select seats to continue';
    buttonReason = count === 0 ? 'Select at least 1 seat' : 'Sign in required';
  } else if (count === 0) {
    buttonText = 'Proceed to checkout';
    buttonReason = 'Select at least 1 seat';
  }

  return (
    <aside
      aria-label="Booking Summary"
      className="w-full lg:w-[32%] sticky top-6 bg-surface-card border border-surface-border rounded-2xl p-6 shadow-2xl flex flex-col justify-between"
    >
      <div>
        {/* Header */}
        <div className="border-b border-surface-border pb-4 mb-4">
          <h2 className="text-lg font-bold text-white tracking-tight">
            Booking Summary
          </h2>
          {show && (
            <p className="text-xs text-gray-400 mt-1">
              {show.title} • {timeStr}
            </p>
          )}
        </div>

        {/* Not Bookable Notice Banner */}
        {!isBookable && (
          <div className="flex items-start space-x-2 p-3 bg-red-950/50 border border-red-500/40 rounded-xl mb-4 text-xs text-red-200">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span>{bookableReason}</span>
          </div>
        )}

        {/* Seats Count & Limit */}
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
          <span>Selected Seats</span>
          <span className={clsx(count === maxSeats ? 'text-amber-400 font-bold' : 'text-gray-300')}>
            {count} / {maxSeats} seats
          </span>
        </div>

        {/* Removable Seat Chips */}
        {count === 0 ? (
          <div className="py-8 text-center border border-dashed border-gray-800 rounded-xl mb-6">
            <p className="text-xs text-gray-500">
              Click seats in the map to select
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 mb-6 max-h-48 overflow-y-auto pr-1">
            {selectedSeats.map((seat) => (
              <div
                key={seat.show_seat_id}
                className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-blue-950/60 border border-blue-500/40 text-blue-200 text-xs font-medium"
              >
                <span>
                  {seat.row_label}{seat.seat_number} ({seat.seat_type[0].toUpperCase()})
                </span>
                <span className="text-blue-300 font-semibold">
                  {formatCurrency(seat.price)}
                </span>
                <button
                  type="button"
                  onClick={() => removeSeat(seat.show_seat_id)}
                  aria-label={`Remove seat ${seat.row_label}${seat.seat_number}`}
                  className="hover:text-white text-blue-400 p-0.5 rounded transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Price Breakdown */}
        <div className="space-y-2.5 border-t border-surface-border pt-4 text-sm text-gray-300 mb-6">
          <div className="flex justify-between">
            <span>Ticket Subtotal</span>
            <span className="font-medium text-white">{formatCurrency(subtotal)}</span>
          </div>
          <div className="flex justify-between text-xs text-gray-400">
            <span>Convenience Fees (incl. taxes)</span>
            <span>{formatCurrency(convenienceFee)}</span>
          </div>
          <div className="border-t border-gray-800 pt-2.5 flex justify-between text-base font-bold text-white">
            <span>Total Amount</span>
            <span className="text-emerald-400 text-lg">{formatCurrency(totalPrice)}</span>
          </div>
        </div>
      </div>

      {/* Primary Action Button */}
      <div>
        {buttonReason && isButtonDisabled && (
          <p className="text-[11px] text-center text-gray-400 mb-2 font-medium">
            {buttonReason}
          </p>
        )}

        <button
          type="button"
          disabled={isButtonDisabled}
          onClick={proceedToCheckout}
          className={clsx(
            'w-full py-3.5 px-4 rounded-xl font-bold text-sm tracking-wide transition-all duration-150 flex items-center justify-center space-x-2 shadow-xl',
            isButtonDisabled
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed border border-gray-700/50'
              : 'bg-blue-600 hover:bg-blue-500 active:scale-[0.99] text-white shadow-blue-600/30 cursor-pointer'
          )}
        >
          {state.isSubmitting ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <>
              <span>{buttonText}</span>
              {!isButtonDisabled && <ArrowRight className="w-4 h-4 ml-1" />}
            </>
          )}
        </button>

        {/* Security & Authenticated badge */}
        <div className="flex items-center justify-center space-x-4 mt-4 text-[11px] text-gray-400">
          <div className="flex items-center space-x-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Secure 5-Min Hold</span>
          </div>
          {user ? (
            <div className="flex items-center space-x-1 text-blue-300">
              <UserCheck className="w-3.5 h-3.5" />
              <span>Signed In</span>
            </div>
          ) : (
            <span>Guest Mode</span>
          )}
        </div>
      </div>
    </aside>
  );
};
