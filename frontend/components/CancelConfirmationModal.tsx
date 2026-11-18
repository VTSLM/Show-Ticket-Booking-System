"use client";

import { useState } from "react";
import { CancelEligibilityResponse } from "@/lib/cancellationsApi";

interface CancelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string, comments: string) => Promise<void>;
  eligibility: CancelEligibilityResponse | null;
  bookingId: string;
  loading: boolean;
}

const CANCELLATION_REASONS = [
  "Change of plans",
  "Selected wrong show or timing",
  "Unable to attend",
  "Payment or booking issue",
  "Other",
];

export default function CancelConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  eligibility,
  bookingId,
  loading,
}: CancelModalProps) {
  const [reason, setReason] = useState(CANCELLATION_REASONS[0]);
  const [comments, setComments] = useState("");

  if (!isOpen || !eligibility) return null;

  const breakdown = eligibility.breakdown;
  const seatsDisplay = eligibility.seats && eligibility.seats.length > 0 
    ? eligibility.seats.join(", ") 
    : "General Admission";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(reason, comments);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div 
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-[#2a2f45] bg-[#121524] text-white shadow-2xl animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="border-b border-[#2a2f45] bg-[#181c30] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-red-500/10 text-red-400 text-lg">
              ⚠️
            </span>
            <div>
              <h2 className="text-lg font-bold text-white">Cancel Booking</h2>
              <p className="text-xs text-gray-400">Booking ID: {bookingId.slice(0, 8)}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-white transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Show summary card */}
          <div className="rounded-xl border border-[#2a2f45] bg-[#161a2e] p-4 text-xs space-y-2">
            <div className="flex justify-between font-semibold text-sm text-gray-200">
              <span>{eligibility.event_title || "Event"}</span>
              <span className="text-blue-400">{eligibility.total_seats} Ticket(s)</span>
            </div>
            <div className="text-gray-400 flex flex-wrap gap-x-4">
              <span>📍 {eligibility.venue_name}, {eligibility.venue_city}</span>
              {eligibility.start_time && (
                <span>🕐 {new Date(eligibility.start_time).toLocaleString("en-IN", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
                })}</span>
              )}
            </div>
            <div className="text-gray-300">
              Seats: <span className="text-gray-100 font-mono font-medium">{seatsDisplay}</span>
            </div>
          </div>

          {/* Refund Breakdown */}
          {breakdown && (
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-blue-300">Refund Summary</h4>
              <div className="flex justify-between text-sm text-gray-300">
                <span>Total Amount Paid</span>
                <span className="font-medium text-white">₹{breakdown.ticket_amount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm text-gray-300">
                <span>Cancellation Processing Charge</span>
                <span className="text-red-400">-₹{breakdown.cancellation_charge.toFixed(2)}</span>
              </div>
              <div className="border-t border-[#2a2f45] pt-2 flex justify-between text-base font-bold text-white">
                <span className="text-emerald-400">Expected Refund</span>
                <span className="text-emerald-400">₹{breakdown.expected_refund.toFixed(2)}</span>
              </div>
              <p className="text-[11px] text-gray-400 mt-1">
                * {breakdown.policy_description || "Refund will be credited back to your original payment method in 5–7 business days."}
              </p>
            </div>
          )}

          {/* Cancellation Reason Dropdown */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Reason for Cancellation <span className="text-red-400">*</span>
            </label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded-lg border border-[#2a2f45] bg-[#181c30] px-3.5 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
              required
            >
              {CANCELLATION_REASONS.map((r) => (
                <option key={r} value={r} className="bg-[#181c30] text-white">
                  {r}
                </option>
              ))}
            </select>
          </div>

          {/* Optional comments */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Additional Feedback (Optional)
            </label>
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Tell us if there's anything else..."
              rows={2}
              className="w-full rounded-lg border border-[#2a2f45] bg-[#181c30] px-3.5 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 rounded-xl border border-[#2a2f45] bg-transparent py-2.5 text-sm font-semibold text-gray-300 hover:bg-[#1a1f36] transition-colors disabled:opacity-50"
            >
              Go Back
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-xl bg-red-600 py-2.5 text-sm font-semibold text-white hover:bg-red-500 transition-colors shadow-lg shadow-red-600/20 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Processing...
                </>
              ) : (
                "Confirm Cancellation"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
