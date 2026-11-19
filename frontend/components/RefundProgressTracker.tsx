"use client";

import { useEffect, useState } from "react";
import { cancellationsApi, RefundStatusResponse } from "@/lib/cancellationsApi";

interface RefundTrackerProps {
  bookingId?: string;
  status?: string;
  refundAmount?: number;
  cancellationCharge?: number;
  razorpayRefundId?: string | null;
  cancelledAt?: string | null;
  completedAt?: string | null;
  failureReason?: string | null;
}

export default function RefundProgressTracker({
  bookingId,
  status: initialStatus,
  refundAmount: initialRefundAmount,
  cancellationCharge: initialCancellationCharge,
  razorpayRefundId: initialRazorpayRefundId,
  cancelledAt: initialCancelledAt,
  completedAt: initialCompletedAt,
  failureReason: initialFailureReason,
}: RefundTrackerProps) {
  const [data, setData] = useState<RefundStatusResponse | null>(null);
  const [loading, setLoading] = useState(!!bookingId);

  useEffect(() => {
    if (!bookingId) return;
    let mounted = true;
    cancellationsApi
      .getRefundStatus(bookingId)
      .then((res) => {
        if (mounted) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [bookingId]);

  const status = data?.refund_status || initialStatus || "NOT_APPLICABLE";
  const refundAmount = data ? data.refund_amount : (initialRefundAmount ?? 0);
  const cancellationCharge = data ? data.cancellation_charge : (initialCancellationCharge ?? 0);
  const razorpayRefundId = data?.refund?.razorpay_refund_id || initialRazorpayRefundId;
  const cancelledAt = data?.cancelled_at || initialCancelledAt;
  const completedAt = data?.refund?.completed_at || initialCompletedAt;
  const failureReason = data?.refund?.failure_reason || initialFailureReason;

  const normStatus = (status || "NOT_APPLICABLE").toUpperCase();

  const steps = [
    { key: "REQUESTED", label: "Cancellation Confirmed", completed: true },
    {
      key: "INITIATED",
      label: "Refund Initiated",
      completed: ["PROCESSING", "PROCESSED", "REFUNDED"].includes(normStatus),
    },
    {
      key: "COMPLETED",
      label: "Refund Credited",
      completed: ["PROCESSED", "REFUNDED"].includes(normStatus),
    },
  ];

  const isFailed = normStatus.includes("FAILED");

  if (loading) {
    return (
      <div className="rounded-2xl border border-[#2a2f45] bg-[#121524] p-5 shadow-lg animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-1/3 mb-4"></div>
        <div className="h-10 bg-gray-800 rounded mb-2"></div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#2a2f45] bg-[#121524] p-5 shadow-lg space-y-4">
      <div className="flex items-center justify-between border-b border-[#2a2f45] pb-3">
        <h3 className="font-bold text-sm text-gray-200 flex items-center gap-2">
          💳 Refund & Cancellation Status
        </h3>
        <span
          className={`px-2.5 py-1 text-xs font-bold rounded-full uppercase tracking-wider ${
            ["PROCESSED", "REFUNDED"].includes(normStatus)
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : isFailed
              ? "bg-red-500/10 text-red-400 border border-red-500/30"
              : ["INITIATED", "PENDING"].includes(normStatus)
              ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
              : "bg-gray-500/10 text-gray-400 border border-gray-500/30"
          }`}
        >
          {normStatus.replace("_", " ")}
        </span>
      </div>

      {/* Progress Steps */}
      <div className="grid grid-cols-3 gap-2 relative">
        {steps.map((step, idx) => (
          <div key={step.key} className="flex flex-col items-center text-center">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                step.completed
                  ? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
                  : isFailed && idx === 1
                  ? "bg-red-500 text-white"
                  : "bg-gray-800 text-gray-400 border border-gray-700"
              }`}
            >
              {step.completed ? "✓" : isFailed && idx === 1 ? "✕" : idx + 1}
            </div>
            <span
              className={`text-[11px] font-medium mt-1.5 ${
                step.completed
                  ? "text-emerald-400"
                  : isFailed && idx === 1
                  ? "text-red-400"
                  : "text-gray-400"
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Status Details Box */}
      <div className="rounded-xl bg-[#090b12] p-3 text-xs space-y-2 border border-[#1d2235]">
        <div className="flex justify-between items-center text-gray-300">
          <span className="text-gray-400">Refund Amount</span>
          <span className="font-semibold text-white">
            ₹{Number(refundAmount || 0).toFixed(2)}
          </span>
        </div>
        {cancellationCharge > 0 && (
          <div className="flex justify-between items-center text-gray-300">
            <span className="text-gray-400">Cancellation Charge Deducted</span>
            <span className="text-gray-400">
              - ₹{Number(cancellationCharge || 0).toFixed(2)}
            </span>
          </div>
        )}
        {razorpayRefundId && (
          <div className="flex justify-between items-center text-gray-300 pt-1 border-t border-[#1d2235]">
            <span className="text-gray-400">Razorpay Refund ID</span>
            <span className="font-mono text-blue-400">{razorpayRefundId}</span>
          </div>
        )}
        {completedAt && (
          <div className="flex justify-between items-center text-gray-300">
            <span className="text-gray-400">Credited At</span>
            <span>{new Date(completedAt).toLocaleString("en-IN")}</span>
          </div>
        )}
        {cancelledAt && !completedAt && (
          <div className="flex justify-between items-center text-gray-300">
            <span className="text-gray-400">Cancelled At</span>
            <span>{new Date(cancelledAt).toLocaleString("en-IN")}</span>
          </div>
        )}
      </div>

      {/* Messages / Alerts */}
      {["INITIATED", "PENDING"].includes(normStatus) && (
        <p className="text-xs text-amber-400/90 leading-relaxed bg-amber-500/5 p-2.5 rounded-lg border border-amber-500/20">
          ℹ️ Your refund is being processed by Razorpay. Funds typically appear in your source bank or payment method within 5–7 business days.
        </p>
      )}

      {["PROCESSED", "REFUNDED"].includes(normStatus) && (
        <p className="text-xs text-emerald-400/90 leading-relaxed bg-emerald-500/5 p-2.5 rounded-lg border border-emerald-500/20">
          ✅ Refund has been processed and credited back to your original payment method.
        </p>
      )}

      {isFailed && (
        <div className="text-xs text-red-400/90 leading-relaxed bg-red-500/5 p-2.5 rounded-lg border border-red-500/20 space-y-1">
          <p className="font-semibold">⚠️ Refund processing encountered an issue</p>
          <p>{failureReason || "Payment gateway processing failure."}</p>
          <p className="text-gray-400">Our support team has been alerted and will manually resolve this refund.</p>
        </div>
      )}
    </div>
  );
}
