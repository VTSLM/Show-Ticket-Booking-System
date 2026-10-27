'use client';

import React from 'react';
import { AlertCircle, Film, RefreshCw } from 'lucide-react';
import { useSeatSelection } from '../context/SeatSelectionContext';
import { ShowBanner } from './ShowBanner';
import { ActiveHoldBanner } from './ActiveHoldBanner';
import { SeatMap } from './SeatMap';
import { SummaryPanel } from './SummaryPanel';
import { ToastContainer } from './ToastContainer';
import { HoldExpiredModal } from './HoldExpiredModal';
import { SeatMapSkeleton } from './SeatMapSkeleton';

export const SeatSelectionView: React.FC = () => {
  const { state, refetchMap } = useSeatSelection();

  // 1. Initial Loading State
  if (!state.mapData) {
    if (state.errorBanner) {
      return (
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-surface-card border border-surface-border rounded-2xl p-8 text-center shadow-2xl">
            <div className="w-12 h-12 bg-red-500/20 text-red-400 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-white mb-2">Unable to Load Show</h2>
            <p className="text-sm text-gray-400 mb-6 leading-relaxed">
              {state.errorBanner}
            </p>
            <button
              type="button"
              onClick={() => refetchMap()}
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry</span>
            </button>
          </div>
        </div>
      );
    }
    return <SeatMapSkeleton />;
  }

  const { show } = state.mapData;

  return (
    <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Top Banner with Movie Metadata & Backdrop */}
      <ShowBanner show={show} reconnecting={state.reconnecting} />

      {/* Active Hold Status Banner (if holding seats) */}
      <ActiveHoldBanner />

      {/* Main Two-Column Desktop Layout (~70% Map, ~30% Sticky Summary) */}
      <div className="flex flex-col lg:flex-row gap-8 items-start">
        <SeatMap />
        <SummaryPanel />
      </div>

      {/* Non-Stacking Bottom Left Toast Notifications */}
      <ToastContainer />

      {/* Hold Expiry Notification Dialog */}
      <HoldExpiredModal />
    </main>
  );
};
