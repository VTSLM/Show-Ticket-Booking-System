"use client";

import { useState, useEffect } from "react";
import { cancellationsApi, AdminCancellationItem } from "@/lib/cancellationsApi";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";

export default function AdminCancellationsPage() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [cancellations, setCancellations] = useState<AdminCancellationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const fetchCancellations = async () => {
    try {
      setLoading(true);
      const data = await cancellationsApi.listAdminCancellations({
        search: search.trim() || undefined,
        refund_status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setCancellations(data || []);
    } catch (err: any) {
      toast.error(err?.message || "Failed to load cancellations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push("/");
      return;
    }
    if (!authLoading && isAdmin) {
      fetchCancellations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin, authLoading]);

  const handleRetry = async (refundId: string) => {
    try {
      setRetryingId(refundId);
      const res = await cancellationsApi.retryRefund(refundId, "Admin manual retry");
      toast.success(`Refund retry dispatched (${res.refund_status})`);
      fetchCancellations();
    } catch (err: any) {
      toast.error(err?.message || "Failed to retry refund");
    } finally {
      setRetryingId(null);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <div className="h-9 w-9 animate-spin rounded-full border-3 border-blue-500 border-t-transparent" />
        <p className="text-sm text-gray-400">Loading cancellation records…</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Cancellation & Refund Management</h1>
          <p className="text-xs text-gray-400 mt-1">Audit cancelled bookings, monitor gateway refunds, and retry failures.</p>
        </div>
        <button
          onClick={fetchCancellations}
          className="px-3.5 py-1.5 rounded-lg border border-[#2a2f45] bg-[#181c30] text-xs font-semibold text-gray-200 hover:bg-[#20253f] transition-colors"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <input
          type="text"
          placeholder="Search by Booking ID, Customer, or Show..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && fetchCancellations()}
          className="rounded-xl border border-[#2a2f45] bg-[#121524] px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border border-[#2a2f45] bg-[#121524] px-4 py-2.5 text-xs text-white focus:border-blue-500 focus:outline-none"
        >
          <option value="all">All Refund Statuses</option>
          <option value="PROCESSED">PROCESSED (Completed)</option>
          <option value="PROCESSING">PROCESSING (Initiated)</option>
          <option value="PENDING">PENDING</option>
          <option value="REFUND_FAILED">FAILED (Action Needed)</option>
          <option value="NOT_APPLICABLE">NOT_APPLICABLE (Unpaid)</option>
        </select>

        <button
          onClick={fetchCancellations}
          className="rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-500 transition-colors"
        >
          Apply Filters
        </button>
      </div>

      {/* Cancellations Table */}
      <div className="overflow-hidden rounded-2xl border border-[#2a2f45] bg-[#121524] shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-[#181c30] text-[11px] uppercase tracking-wider text-gray-400 border-b border-[#2a2f45]">
              <tr>
                <th className="py-3.5 px-4 font-semibold">Booking / Event</th>
                <th className="py-3.5 px-4 font-semibold">Customer</th>
                <th className="py-3.5 px-4 font-semibold">Financials</th>
                <th className="py-3.5 px-4 font-semibold">Refund Status</th>
                <th className="py-3.5 px-4 font-semibold">Reason</th>
                <th className="py-3.5 px-4 font-semibold">Cancelled At</th>
                <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e2338]">
              {cancellations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-gray-500">
                    No cancellation records match the criteria.
                  </td>
                </tr>
              ) : (
                cancellations.map((item) => {
                  const status = (item.refund_status || "NOT_APPLICABLE").toUpperCase();
                  const isFailed = status.includes("FAILED");

                  return (
                    <tr key={item.booking_id} className="hover:bg-[#181c30]/50 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white">{item.event_title}</div>
                        <div className="font-mono text-[11px] text-gray-400">#{item.booking_id.slice(0, 8)}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-gray-200">{item.customer_name}</div>
                        <div className="text-[11px] text-gray-500">{item.customer_email}</div>
                      </td>
                      <td className="py-3.5 px-4 space-y-0.5">
                        <div>Paid: <span className="text-white font-medium">₹{Number(item.total_amount).toFixed(2)}</span></div>
                        <div className="text-emerald-400 font-semibold">Refund: ₹{Number(item.refund_amount).toFixed(2)}</div>
                        {item.cancellation_charge > 0 && (
                          <div className="text-[10px] text-red-400">Fee: ₹{Number(item.cancellation_charge).toFixed(2)}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            ["PROCESSED", "REFUNDED"].includes(status)
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              : isFailed
                              ? "bg-red-500/10 text-red-400 border border-red-500/30"
                              : status === "NOT_APPLICABLE"
                              ? "bg-gray-500/10 text-gray-400"
                              : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                          }`}
                        >
                          {status}
                        </span>
                        {item.razorpay_refund_id && (
                          <div className="font-mono text-[10px] text-gray-500 mt-1">{item.razorpay_refund_id}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="font-medium text-gray-200 truncate">{item.cancellation_reason}</div>
                        {item.cancellation_notes && (
                          <div className="text-[11px] text-gray-400 italic truncate">{item.cancellation_notes}</div>
                        )}
                        {item.failure_reason && (
                          <div className="text-[10px] text-red-400 mt-1">{item.failure_reason}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-gray-400 whitespace-nowrap text-[11px]">
                        {item.cancelled_at
                          ? new Date(item.cancelled_at).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        {isFailed && item.refund_id ? (
                          <button
                            onClick={() => handleRetry(item.refund_id!)}
                            disabled={retryingId === item.refund_id}
                            className="rounded-lg bg-amber-600 px-3 py-1 text-[11px] font-semibold text-white hover:bg-amber-500 disabled:opacity-50 transition-colors shadow-sm"
                          >
                            {retryingId === item.refund_id ? "Retrying..." : "Retry Refund"}
                          </button>
                        ) : (
                          <span className="text-gray-500 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
