"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { organizerAdminApi } from "@/lib/api";

export default function AdminOrganizersPage() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [organizers, setOrganizers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");

  // Modals
  const [actionModal, setActionModal] = useState<{
    open: boolean;
    organizer: any | null;
    action: "SUSPEND" | "REACTIVATE" | null;
  }>({ open: false, organizer: null, action: null });
  const [actionReason, setActionReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Payout eligibility modal
  const [payoutModal, setPayoutModal] = useState<{
    open: boolean;
    data: any | null;
    loading: boolean;
  }>({ open: false, data: null, loading: false });

  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push("/");
      return;
    }
    if (!authLoading && isAdmin) {
      fetchOrganizers();
    }
  }, [authLoading, isAdmin, statusFilter, tierFilter]);

  const fetchOrganizers = async () => {
    try {
      setLoading(true);
      const res = await organizerAdminApi.listOrganizers({
        q: searchQuery || undefined,
        status: statusFilter || undefined,
        tier: tierFilter || undefined,
        limit: 50,
        offset: 0,
      });
      setOrganizers(res.organizers || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      toast.error(err.message || "Failed to load organizers directory");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchOrganizers();
  };

  const executeAccountAction = async () => {
    if (!actionModal.organizer || !actionModal.action) return;
    if (!actionReason.trim()) {
      toast.error("Please provide a reason for this administrative action.");
      return;
    }

    try {
      setActionLoading(true);
      if (actionModal.action === "SUSPEND") {
        await organizerAdminApi.suspendOrganizer(
          actionModal.organizer.id,
          actionReason
        );
        toast.success(`Organizer '${actionModal.organizer.legal_name}' suspended.`);
      } else {
        await organizerAdminApi.reactivateOrganizer(
          actionModal.organizer.id,
          actionReason
        );
        toast.success(`Organizer '${actionModal.organizer.legal_name}' reactivated.`);
      }
      setActionModal({ open: false, organizer: null, action: null });
      setActionReason("");
      await fetchOrganizers();
    } catch (err: any) {
      toast.error(err.message || "Failed to execute account action");
    } finally {
      setActionLoading(false);
    }
  };

  const checkPayoutEligibility = async (org: any) => {
    try {
      setPayoutModal({ open: true, data: null, loading: true });
      const res = await organizerAdminApi.getPayoutEligibility(org.id);
      setPayoutModal({ open: true, data: res, loading: false });
    } catch (err: any) {
      toast.error(err.message || "Could not evaluate payout eligibility");
      setPayoutModal({ open: false, data: null, loading: false });
    }
  };

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-[#070c18] text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="text-sm text-gray-400">Loading organizer directory...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#070c18] text-white px-4 py-8 sm:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <div className="text-xs font-semibold tracking-wider text-blue-400 uppercase">
              Administrator Directory
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white mt-1">
              Organizer directory
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Manage organizer accounts, inspect trust tiers, and enforce compliance actions.
            </p>
          </div>
          <div className="text-xs text-gray-400 font-medium">
            Total Organizers: <span className="text-white font-bold">{total}</span>
          </div>
        </header>

        {/* Filter Bar */}
        <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-4 flex flex-col md:flex-row gap-3 items-center justify-between">
          <form onSubmit={handleSearchSubmit} className="w-full md:w-96 flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, state, or email..."
              className="w-full bg-[#050b14] border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold rounded-xl bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            >
              Search
            </button>
          </form>

          <div className="flex items-center gap-3 w-full md:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#050b14] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="APPROVED">APPROVED</option>
              <option value="SUBMITTED">SUBMITTED</option>
              <option value="IN_REVIEW">IN_REVIEW</option>
              <option value="CHANGES_REQUESTED">CHANGES_REQUESTED</option>
              <option value="REJECTED">REJECTED</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="DRAFT">DRAFT</option>
            </select>

            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="bg-[#050b14] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">All Tiers</option>
              <option value="TIER_1">TIER_1 (Starter)</option>
              <option value="TIER_2">TIER_2 (Established)</option>
              <option value="TIER_3">TIER_3 (High Volume)</option>
            </select>
          </div>
        </div>

        {/* Organizers Table / Cards */}
        {organizers.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-[#0b1426] p-12 text-center text-gray-400 text-sm">
            No organizers found matching current search and filters.
          </div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-[#0b1426] overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="border-b border-white/10 bg-[#080f1e] text-[11px] uppercase tracking-wider text-gray-400">
                <tr>
                  <th className="py-3 px-4">Organizer Entity</th>
                  <th className="py-3 px-4">Business Type</th>
                  <th className="py-3 px-4">State</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Trust Tier</th>
                  <th className="py-3 px-4">Contact</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {organizers.map((org) => (
                  <tr key={org.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{org.legal_name}</div>
                      <div className="text-[11px] text-gray-500 font-mono">
                        PAN: {org.pan_masked || "N/A"}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-300">{org.business_type}</td>
                    <td className="py-3 px-4 text-gray-400">{org.state || "—"}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                          org.verification_status === "APPROVED"
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            : org.verification_status === "SUSPENDED"
                            ? "bg-red-500/20 text-red-300 border border-red-500/30"
                            : org.verification_status === "REJECTED"
                            ? "bg-rose-500/20 text-rose-300"
                            : "bg-blue-500/20 text-blue-300"
                        }`}
                      >
                        {org.verification_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                        {org.trust_tier}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div>{org.contact_name}</div>
                      <div className="text-[11px] text-gray-500">{org.contact_email}</div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => checkPayoutEligibility(org)}
                          className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors"
                        >
                          Payout Rules
                        </button>

                        {org.verification_status === "SUSPENDED" ? (
                          <button
                            onClick={() =>
                              setActionModal({
                                open: true,
                                organizer: org,
                                action: "REACTIVATE",
                              })
                            }
                            className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 transition-colors"
                          >
                            Reactivate
                          </button>
                        ) : org.verification_status === "APPROVED" ? (
                          <button
                            onClick={() =>
                              setActionModal({
                                open: true,
                                organizer: org,
                                action: "SUSPEND",
                              })
                            }
                            className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 transition-colors"
                          >
                            Suspend
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Account Action Modal (Suspend / Reactivate) */}
      {actionModal.open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b1426] border border-white/10 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">
              {actionModal.action === "SUSPEND"
                ? `Suspend Organizer: ${actionModal.organizer?.legal_name}`
                : `Reactivate Organizer: ${actionModal.organizer?.legal_name}`}
            </h3>
            <p className="text-xs text-gray-400">
              {actionModal.action === "SUSPEND"
                ? "Suspension halts live ticket sales, freezes payout settlement eligibility, and records an audit log event."
                : "Reactivation restores verification standing and settlement eligibility."}
            </p>

            <textarea
              rows={3}
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              placeholder="Enter mandatory justification reason..."
              className="w-full bg-[#050b14] border border-white/10 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-blue-500"
            />

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setActionModal({ open: false, organizer: null, action: null });
                  setActionReason("");
                }}
                className="px-4 py-2 text-xs text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={executeAccountAction}
                disabled={actionLoading}
                className={`px-4 py-2 text-xs font-semibold rounded-lg text-white ${
                  actionModal.action === "SUSPEND"
                    ? "bg-red-600 hover:bg-red-500"
                    : "bg-emerald-600 hover:bg-emerald-500"
                }`}
              >
                Confirm {actionModal.action}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payout Eligibility Modal */}
      {payoutModal.open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b1426] border border-white/10 rounded-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-bold text-white">
                Payout Settlement Eligibility
              </h3>
              <button
                onClick={() => setPayoutModal({ open: false, data: null, loading: false })}
                className="text-gray-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {payoutModal.loading ? (
              <p className="text-xs text-gray-400 py-6 text-center">
                Evaluating settlement rules...
              </p>
            ) : payoutModal.data ? (
              <div className="space-y-4">
                <div
                  className={`p-4 rounded-xl border text-xs ${
                    payoutModal.data.eligible
                      ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-300"
                      : "bg-red-950/20 border-red-500/30 text-red-300"
                  }`}
                >
                  <div className="font-bold text-sm mb-1">
                    {payoutModal.data.eligible
                      ? "✓ ELIGIBLE FOR SETTLEMENT PAYOUTS"
                      : "✗ INELIGIBLE FOR PAYOUT SETTLEMENT"}
                  </div>
                  <ul className="list-disc pl-4 space-y-1 mt-2 text-[11px]">
                    {payoutModal.data.reasons.map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs bg-[#050b14] p-4 rounded-xl border border-white/5">
                  <div>
                    <span className="text-gray-500">Trust Tier</span>
                    <p className="font-bold text-white">{payoutModal.data.trust_tier}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Payout Hold Days</span>
                    <p className="font-bold text-white">{payoutModal.data.payout_hold_days} days</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Max Live Shows</span>
                    <p className="font-bold text-white">{payoutModal.data.max_live_shows} shows</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Instant Settlement</span>
                    <p className="font-bold text-white">
                      {payoutModal.data.instant_payout ? "Enabled" : "Disabled"}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </main>
  );
}

