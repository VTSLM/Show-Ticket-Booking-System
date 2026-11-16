"use client";

import { useState } from "react";

interface TermsAndConditionsModalProps {
  isOpen: boolean;
  eventTitle: string;
  venueName: string;
  showTime?: string;
  termsText: string;
  termsHash: string;
  isDefaultTerms: boolean;
  holdSecondsLeft?: number;
  isSubmitting: boolean;
  onAccept: (termsHash: string, termsText: string) => void;
  onCancel: () => void;
}

export default function TermsAndConditionsModal({
  isOpen,
  eventTitle,
  venueName,
  showTime,
  termsText,
  termsHash,
  isDefaultTerms,
  holdSecondsLeft,
  isSubmitting,
  onAccept,
  onCancel,
}: TermsAndConditionsModalProps) {
  const [agreed, setAgreed] = useState(false);

  if (!isOpen) return null;

  const formatTimer = (seconds?: number) => {
    if (seconds == null || seconds <= 0) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const handleContinue = () => {
    if (!agreed || isSubmitting) return;
    onAccept(termsHash, termsText);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-modal-title"
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-slate-700 bg-[#0e121d] shadow-2xl shadow-black/90"
      >
        {/* Modal Header */}
        <div className="border-b border-slate-800 bg-[#131726] px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">
                Step 2 of 2: Show Terms &amp; Policies
              </span>
              <h2 id="terms-modal-title" className="text-lg font-bold text-white">
                Terms &amp; Conditions
              </h2>
            </div>
            {holdSecondsLeft != null && (
              <div
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-mono font-bold ${
                  holdSecondsLeft < 120
                    ? "border-red-500/50 bg-red-950/40 text-red-400 animate-pulse"
                    : "border-amber-500/40 bg-amber-950/30 text-amber-300"
                }`}
              >
                <span>⏱ Hold expires in:</span>
                <span>{formatTimer(holdSecondsLeft)}</span>
              </div>
            )}
          </div>

          {/* Show Context Pill */}
          <div className="mt-2 text-xs text-slate-300">
            <span className="font-semibold text-white">{eventTitle}</span> • 📍 {venueName}
            {showTime && ` • 🗓 ${showTime}`}
          </div>
        </div>

        {/* Modal Body: Scrollable Terms Content */}
        <div className="p-6">
          <div className="flex items-center justify-between pb-2 text-xs text-slate-400">
            <span>Please read carefully before payment:</span>
            <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
              {isDefaultTerms ? "TicketFlow Standard Terms" : "Show-Specific Organizer Terms"}
            </span>
          </div>

          <div
            tabIndex={0}
            className="max-h-60 overflow-y-auto rounded-xl border border-slate-800 bg-[#090b12] p-4 text-xs leading-relaxed text-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <p className="whitespace-pre-line font-sans">
              {termsText || "Standard entry guidelines and platform terms apply. Carry a valid government ID."}
            </p>
          </div>

          {/* Mandatory Checkbox */}
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-3">
            <input
              type="checkbox"
              id="agree-checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-700 bg-slate-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-[#090b12]"
            />
            <label
              htmlFor="agree-checkbox"
              className="cursor-pointer select-none text-xs text-slate-200"
            >
              I have read and agree to the <span className="font-semibold text-white">Terms and Conditions</span> for this show.
            </label>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-800 bg-[#131726]/60 px-6 py-4">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="rounded-xl border border-slate-700 bg-slate-800/70 px-4 py-2.5 text-xs font-semibold text-slate-300 transition hover:bg-slate-700 hover:text-white"
          >
            Cancel &amp; Return to Seats
          </button>
          <button
            type="button"
            onClick={handleContinue}
            disabled={!agreed || isSubmitting}
            className={`inline-flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-xs font-bold text-white transition ${
              agreed && !isSubmitting
                ? "bg-blue-600 shadow-md shadow-blue-600/30 hover:bg-blue-500 active:scale-95"
                : "cursor-not-allowed bg-slate-800 text-slate-500 opacity-60"
            }`}
          >
            {isSubmitting ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-white" />
                <span>Recording Acceptance…</span>
              </>
            ) : (
              <span>Accept &amp; Continue to Payment →</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
