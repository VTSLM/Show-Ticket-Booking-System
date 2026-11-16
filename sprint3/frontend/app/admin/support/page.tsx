"use client";
// app/admin/support/page.tsx
// Customer Care — Admin Dashboard (Hari, Sprint 2 — item 5)
// Shows all support tickets with status/category filters and a search box.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  supportAdminApi,
  SupportRequestSummary,
  SupportStatus,
  SupportCategory,
  CATEGORY_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
  formatDateTime,
} from "@/lib/supportAdminApi";

const STATUS_TABS: (SupportStatus | "all")[] = ["all", "open", "in_progress", "resolved", "closed"];
const CATEGORY_FILTERS: (SupportCategory | "all")[] = ["all", "payment", "booking", "refund", "account", "other"];

export default function AdminSupportDashboard() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [requests, setRequests] = useState<SupportRequestSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusTab, setStatusTab] = useState<SupportStatus | "all">("all");
  const [category, setCategory] = useState<SupportCategory | "all">("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(() => {
    setLoading(true);
    return supportAdminApi
      .list({
        status: statusTab !== "all" ? statusTab : undefined,
        category: category !== "all" ? category : undefined,
        search: debouncedSearch || undefined,
      })
      .then(setRequests)
      .catch((err: Error) => toast.error(err.message || "Could not load requests"))
      .finally(() => setLoading(false));
  }, [statusTab, category, debouncedSearch]);

  useEffect(() => {
    if (!authLoading && !isAdmin) { router.push("/"); return; }
    if (!authLoading && isAdmin) load();
  }, [isAdmin, authLoading, load, router]);

  const counts = STATUS_TABS.reduce((acc, t) => {
    acc[t] = t === "all" ? requests.length : 0; // server already filters
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Support Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            {loading ? "Loading…" : `${requests.length} request${requests.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Link href="/admin" className="btn-secondary text-sm">← Admin Home</Link>
      </div>

      {/* Filters row */}
      <div className="card p-4 mb-6 space-y-3">
        {/* Search */}
        <input
          type="search"
          className="input"
          placeholder="Search subject or request number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search requests"
        />

        {/* Status tabs */}
        <div className="flex flex-wrap gap-2">
          {STATUS_TABS.map((t) => (
            <button
              key={t}
              onClick={() => setStatusTab(t)}
              className={`text-sm px-3 py-1 rounded-full border transition-colors ${
                statusTab === t
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-slate-900 text-slate-300 border-slate-700 hover:border-blue-500"
              }`}
            >
              {t === "all" ? "All statuses" : STATUS_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Category filters */}
        <div className="flex flex-wrap gap-2">
          {CATEGORY_FILTERS.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                category === c
                  ? "bg-slate-600 text-white border-slate-600"
                  : "bg-slate-900 text-slate-400 border-slate-700 hover:border-slate-500"
              }`}
            >
              {c === "all" ? "All categories" : CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket list */}
      {loading ? (
        <div className="text-center py-16 text-slate-500">Loading…</div>
      ) : requests.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p className="text-4xl mb-4">🎧</p>
          <p>No support requests match your filters.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((r) => {
            const needsAttention =
              !r.last_reply_by_admin && (r.status === "open" || r.status === "in_progress");
            return (
              <Link
                key={r.id}
                href={`/admin/support/${r.id}`}
                className="card p-5 flex gap-4 hover:-translate-y-0.5 hover:border-blue-500/70 transition"
              >
                {/* Priority dot */}
                <div className="flex-shrink-0 mt-1">
                  <span
                    className={`inline-block w-2.5 h-2.5 rounded-full ${
                      r.priority === "high"
                        ? "bg-red-500"
                        : r.priority === "low"
                        ? "bg-slate-600"
                        : "bg-yellow-500"
                    }`}
                    title={`Priority: ${r.priority}`}
                  />
                </div>

                {/* Main info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="text-xs text-slate-500 font-mono">{r.request_number}</p>
                    {needsAttention && (
                      <span className="text-xs text-orange-400 font-semibold">● Awaiting reply</span>
                    )}
                  </div>
                  <h3 className="font-semibold text-white truncate">{r.subject}</h3>
                  <p className="text-slate-400 text-sm">
                    {r.user_name} · {CATEGORY_LABELS[r.category]}
                  </p>
                  <p className="text-slate-500 text-xs mt-1">
                    {r.message_count} message{r.message_count !== 1 ? "s" : ""} · updated {formatDateTime(r.updated_at)}
                  </p>
                </div>

                {/* Status badge */}
                <div className="flex-shrink-0 self-center">
                  <span
                    className={`text-xs px-2.5 py-1 rounded-full whitespace-nowrap font-medium ${STATUS_STYLES[r.status]}`}
                  >
                    {STATUS_LABELS[r.status]}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
