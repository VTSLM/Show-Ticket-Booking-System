import React from 'react';
import { Clock, RefreshCw } from 'lucide-react';
import { useSeatSelection } from '../context/SeatSelectionContext';

export const HoldExpiredModal: React.FC = () => {
  const { state, dispatch, refetchMap } = useSeatSelection();

  if (!state.holdExpiredModalOpen) return null;

  const handleAcknowledge = async () => {
    dispatch({ type: 'CLOSE_HOLD_EXPIRED_MODAL' });
    await refetchMap();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="expired-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in"
    >
      <div className="w-full max-w-md bg-surface-card border border-surface-border rounded-2xl p-6 shadow-2xl text-center">
        <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mx-auto mb-4">
          <Clock className="w-6 h-6" />
        </div>

        <h3 id="expired-modal-title" className="text-lg font-semibold text-white mb-2">
          Your seat hold has expired
        </h3>

        <p className="text-sm text-gray-300 mb-6 leading-relaxed">
          Seat reservations are held for 5 minutes to keep ticket inventory fair for all fans.
          The held seats have been released back to the auditorium.
        </p>

        <button
          type="button"
          onClick={handleAcknowledge}
          className="w-full inline-flex items-center justify-center space-x-2 px-5 py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-colors duration-150 shadow-lg"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Select New Seats</span>
        </button>
      </div>
    </div>
  );
};
