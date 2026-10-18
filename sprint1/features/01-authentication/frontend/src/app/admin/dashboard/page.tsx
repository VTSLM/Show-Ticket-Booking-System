"use client";
// src/app/admin/dashboard/page.tsx — Admin dashboard with pending-approval management.

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { fetchPendingUsers, approveUser, PendingUser } from "@/lib/api";

export default function AdminDashboardPage() {
  const { profile, firebaseUser, loading, logout } = useAuth();
  const router = useRouter();

  const [pending, setPending] = useState<PendingUser[]>([]);
  const [fetchingPending, setFetchingPending] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ---- guard ----
  useEffect(() => {
    if (loading) return;
    if (!profile) { router.push("/login"); return; }
    if (!profile.roles.includes("admin")) { router.push("/"); return; }
  }, [loading, profile, router]);

  // ---- load pending ----
  const loadPending = useCallback(async () => {
    if (!firebaseUser) return;
    setFetchingPending(true);
    try {
      const token = await firebaseUser.getIdToken();
      const list = await fetchPendingUsers(token);
      setPending(list);
    } catch {
      toast.error("Failed to load pending users.");
    } finally {
      setFetchingPending(false);
    }
  }, [firebaseUser]);

  useEffect(() => { loadPending(); }, [loadPending]);

  // ---- approve / reject ----
  const handleAction = async (userId: string, action: "approve" | "reject") => {
    if (!firebaseUser) return;
    setActionLoading(userId + action);
    try {
      const token = await firebaseUser.getIdToken();
      await approveUser(token, userId, action);
      toast.success(action === "approve" ? "User approved ✓" : "User rejected.");
      await loadPending();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading || !profile) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Top nav */}
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🛡️</span>
          <div>
            <h1 className="text-lg font-bold">Admin Dashboard</h1>
            <p className="text-xs text-gray-400">ShowBook Platform</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">
            {profile.name} &middot; <span className="text-brand-400 capitalize">{profile.roles[0]}</span>
          </span>
          <button
            onClick={logout}
            className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800 transition"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-10 sm:grid-cols-3">
          <StatCard icon="⏳" label="Pending Approvals" value={pending.length} highlight={pending.length > 0} />
          <StatCard icon="✅" label="Platform Status" value="Active" />
          <StatCard icon="👤" label="Logged in as" value="Administrator" />
        </div>

        {/* Pending approvals table */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Pending Registrations</h2>
            <button
              onClick={loadPending}
              disabled={fetchingPending}
              className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800 transition disabled:opacity-50"
            >
              {fetchingPending ? (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                "↻"
              )}
              Refresh
            </button>
          </div>

          {fetchingPending && pending.length === 0 ? (
            <div className="py-20 text-center text-gray-500">Loading…</div>
          ) : pending.length === 0 ? (
            <div className="rounded-xl border border-gray-800 bg-gray-900 py-16 text-center">
              <span className="text-4xl">🎉</span>
              <p className="mt-3 text-gray-400">No pending approvals</p>
            </div>
          ) : (
            <div className="space-y-3">
              {pending.map((u) => (
                <div
                  key={u.user_id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-gray-800 bg-gray-900 px-5 py-4"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-white truncate">{u.name}</p>
                    <p className="text-sm text-gray-400 truncate">{u.email}</p>
                    <span className="mt-1 inline-block rounded-full bg-brand-900/50 border border-brand-700/50 px-2 py-0.5 text-xs capitalize text-brand-300">
                      {u.requested_role}
                    </span>
                    <p className="mt-1 text-xs text-gray-600">
                      Registered {new Date(u.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleAction(u.user_id, "approve")}
                      disabled={actionLoading !== null}
                      className="flex items-center gap-1.5 rounded-lg bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-600 transition disabled:opacity-50"
                    >
                      {actionLoading === u.user_id + "approve" ? (
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      ) : "✓"}
                      Approve
                    </button>
                    <button
                      onClick={() => handleAction(u.user_id, "reject")}
                      disabled={actionLoading !== null}
                      className="flex items-center gap-1.5 rounded-lg bg-red-800 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition disabled:opacity-50"
                    >
                      {actionLoading === u.user_id + "reject" ? (
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      ) : "✕"}
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: string;
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? "border-amber-700/50 bg-amber-900/20"
          : "border-gray-800 bg-gray-900"
      }`}
    >
      <span className="text-2xl">{icon}</span>
      <p className="mt-2 text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-gray-400">{label}</p>
    </div>
  );
}
