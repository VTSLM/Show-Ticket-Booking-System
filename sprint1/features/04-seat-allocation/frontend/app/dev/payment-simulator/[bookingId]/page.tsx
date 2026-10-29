'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { CreditCard, CheckCircle, AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react';
import { apiClient } from '@/features/seat-selection/services/apiClient';
import { HoldDetailResponse } from '@/features/seat-selection/types/api';
import { formatCurrency } from '@/features/seat-selection/utils/formatters';

interface SimulatorProps {
  params: {
    bookingId: string;
  };
}

export default function PaymentSimulatorPage({ params }: SimulatorProps) {
  const { bookingId } = params;
  const isEnabled = process.env.NEXT_PUBLIC_ENABLE_DEV_PAYMENT_SIMULATOR === 'true';

  const [hold, setHold] = useState<HoldDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isEnabled) return;

    apiClient
      .getHold(bookingId)
      .then((data) => {
        setHold(data);
        if (data.status === 'confirmed') {
          setSuccess(true);
        }
      })
      .catch((err) => {
        setErrorMsg(err.message || 'Failed to fetch hold details for checkout.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [bookingId, isEnabled]);

  if (!isEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-surface-card border border-surface-border rounded-2xl p-8 max-w-md text-center">
          <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-2">Simulator Disabled</h2>
          <p className="text-sm text-gray-400">
            The local payment confirmation simulator is disabled in this environment.
          </p>
        </div>
      </div>
    );
  }

  const handleSimulatePayment = async () => {
    setSimulating(true);
    setErrorMsg(null);
    try {
      await apiClient.simulatePayment(bookingId);
      setSuccess(true);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Payment simulation failed.');
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="min-h-screen bg-background py-12 px-4 sm:px-6">
      <div className="max-w-lg mx-auto bg-surface-card border border-surface-border rounded-2xl p-6 sm:p-8 shadow-2xl">
        <div className="flex items-center space-x-3 pb-6 border-b border-surface-border mb-6">
          <div className="p-3 bg-blue-500/20 text-blue-400 rounded-xl">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Dev Payment Simulator</h1>
            <p className="text-xs text-gray-400">Local verification of post-hold payment flow</p>
          </div>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-sm text-gray-400">Fetching booking details...</p>
          </div>
        ) : errorMsg ? (
          <div className="p-4 bg-red-950/40 border border-red-500/40 rounded-xl mb-6 text-sm text-red-200">
            {errorMsg}
          </div>
        ) : success ? (
          <div className="text-center py-6 space-y-4">
            <div className="w-14 h-14 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-white">Payment Confirmed!</h2>
            <p className="text-xs text-gray-300">
              Booking <span className="font-mono text-emerald-400">{hold?.booking_number}</span> has been confirmed.
              The associated seats are now permanently marked as <span className="font-semibold text-white">booked</span>.
            </p>
            {hold?.show_id && (
              <Link
                href={`/shows/${hold.show_id}/seats`}
                className="inline-flex items-center space-x-2 text-sm text-blue-400 hover:text-blue-300 mt-4"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Return to Seat Map</span>
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            <div className="bg-surface-hover/60 rounded-xl p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Booking Reference</span>
                <span className="font-mono text-white font-semibold">{hold?.booking_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Seats Reserved</span>
                <span className="font-medium text-white">{hold?.show_seat_ids.length} seats</span>
              </div>
              <div className="flex justify-between border-t border-gray-700/60 pt-2 font-bold text-base">
                <span className="text-white">Amount Due</span>
                <span className="text-emerald-400">{formatCurrency(hold?.total_amount || 0)}</span>
              </div>
            </div>

            <button
              type="button"
              disabled={simulating}
              onClick={handleSimulatePayment}
              className="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg transition-colors flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {simulating ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <span>Simulate Successful Payment</span>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
