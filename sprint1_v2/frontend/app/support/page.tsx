"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  supportApi,
  SupportRequestSummary,
  SupportStatus,
  CATEGORY_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
  formatDateTime,
} from "@/lib/supportApi";

const TABS: (SupportStatus | "all")[] = ["all", "open", "in_progress", "resolved", "closed"];

export default function MySupportRequestsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [requests, setRequests] = useState<SupportRequestSummary[]>([]);
  const [tab, setTab] = useState<SupportStatus | "all">("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    if (user) {
      supportApi
        .list()
        .then(setRequests)
        .catch(err => toast.error(err.message || "Could not load your requests"))
        .finally(() => setLoading(false));
    }
  }, [user, authLoading, router]);

  if (loading || authLoading) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  const shown = tab === "all" ? requests : requests.filter(r => r.status === tab);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6 gap-4">
        <h1 className="text-3xl font-bold">My Support Requests</h1>
        <Link href="/support/new" className="btn-primary text-sm whitespace-nowrap">+ New Request</Link>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map(t => {
          const count = t === "all" ? requests.length : requests.filter(r => r.status === t).length;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-sm px-3 py-1 rounded-full border transition-colors ${
                tab === t
                  ? "bg-red-500 text-white border-red-500"
                  : "bg-white text-gray-700 border-gray-300 hover:border-red-400"
              }`}
            >
              {t === "all" ? "All" : STATUS_LABELS[t]} ({count})
            </button>
          );
        })}
      </div>

      {shown.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-4">💬</p>
          <p>{requests.length === 0 ? "You haven't raised any support requests." : "Nothing here."}</p>
          <Link href="/help" className="text-red-500 hover:underline text-sm mt-2 inline-block">
            Check the Help Centre for quick answers
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {shown.map(r => {
            const newReply = r.last_reply_by_admin && (r.status === "open" || r.status === "in_progress");
            return (
              <Link key={r.id} href={`/support/${r.id}`} className="card flex gap-4 hover:shadow-lg transition-shadow">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-400 font-mono">{r.request_number}</p>
                  <h3 className="font-semibold text-lg truncate">{r.subject}</h3>
                  <p className="text-gray-500 text-sm">
                    {CATEGORY_LABELS[r.category]}
                    {r.booking_number && <> • Booking {r.booking_number}</>}
                  </p>
                  <p className="text-gray-400 text-xs mt-1">Last updated {formatDateTime(r.updated_at)}</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${STATUS_STYLES[r.status]}`}>
                    {STATUS_LABELS[r.status]}
                  </span>
                  {newReply && (
                    <span className="text-xs text-red-500 font-semibold whitespace-nowrap">● Support replied</span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
