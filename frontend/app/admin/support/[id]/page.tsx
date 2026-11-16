"use client";
// app/admin/support/[id]/page.tsx
// Customer Care — Admin ticket detail + reply + status change
// (Hari, Sprint 2 — items 6 & 7)

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  supportAdminApi,
  SupportRequestDetail,
  SupportStatus,
  CATEGORY_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
  formatDateTime,
} from "@/lib/supportAdminApi";

const ALL_STATUSES: SupportStatus[] = ["open", "in_progress", "resolved", "closed"];

export default function AdminTicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [request, setRequest] = useState<SupportRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [replyStatus, setReplyStatus] = useState<SupportStatus | "">("");
  const [sending, setSending] = useState(false);
  const [changingStatus, setChangingStatus] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    return supportAdminApi
      .get(id)
      .then((r) => {
        setRequest(r);
        setReplyStatus(r.status);
      })
      .catch(() => setRequest(null))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!authLoading && !isAdmin) { router.push("/"); return; }
    if (!authLoading && isAdmin && id) load();
  }, [isAdmin, authLoading, id, router, load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [request?.messages?.length]);

  const handleReply = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = replyText.trim();
    if (!text || !request) return;
    setSending(true);
    try {
      await supportAdminApi.reply(request.id, {
        message: text,
        status: (replyStatus || request.status) as SupportStatus,
      });
      toast.success("Reply sent");
      setReplyText("");
      setLoading(true);
      await load();
    } catch (err: any) {
      toast.error(err.message || "Could not send reply");
    } finally {
      setSending(false);
    }
  };

  const handleStatusOnly = async (newStatus: SupportStatus) => {
    if (!request) return;
    setChangingStatus(true);
    try {
      await supportAdminApi.setStatus(request.id, newStatus);
      toast.success(`Status changed to ${STATUS_LABELS[newStatus]}`);
      setRequest((prev) => prev ? { ...prev, status: newStatus } : prev);
      setReplyStatus(newStatus);
    } catch (err: any) {
      toast.error(err.message || "Could not change status");
    } finally {
      setChangingStatus(false);
    }
  };

  if (authLoading || loading) {
    return <div className="text-center py-20 text-slate-500">Loading…</div>;
  }

  if (!request) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">Support request not found.</p>
        <Link href="/admin/support" className="btn-secondary">← Back to Dashboard</Link>
      </div>
    );
  }

  const isClosed = request.status === "closed";

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Back link */}
      <Link href="/admin/support" className="text-sm text-slate-400 hover:text-blue-400">
        ← Support Dashboard
      </Link>

      {/* Request meta card */}
      <div className="card p-6 mt-2 mb-6">
        <div className="flex justify-between items-start gap-4 mb-4">
          <div className="min-w-0">
            <p className="text-xs text-slate-500 font-mono">{request.request_number}</p>
            <h1 className="text-2xl font-bold text-white break-words">{request.subject}</h1>
          </div>
          <span
            className={`text-xs px-3 py-1 rounded-full font-semibold whitespace-nowrap ${STATUS_STYLES[request.status]}`}
          >
            {STATUS_LABELS[request.status]}
          </span>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-4">
          <dt className="text-slate-400">Customer</dt>
          <dd className="text-white">{request.user_name}</dd>
          <dt className="text-slate-400">Email</dt>
          <dd className="text-white break-all">{request.user_email}</dd>
          <dt className="text-slate-400">Category</dt>
          <dd>{CATEGORY_LABELS[request.category]}</dd>
          {request.booking_number && (
            <>
              <dt className="text-slate-400">Booking</dt>
              <dd className="text-blue-400">{request.booking_number}</dd>
            </>
          )}
          <dt className="text-slate-400">Opened</dt>
          <dd>{formatDateTime(request.created_at)}</dd>
          <dt className="text-slate-400">Priority</dt>
          <dd>
            <span
              className={`font-semibold ${
                request.priority === "high"
                  ? "text-red-400"
                  : request.priority === "low"
                  ? "text-slate-400"
                  : "text-yellow-400"
              }`}
            >
              {request.priority.charAt(0).toUpperCase() + request.priority.slice(1)}
            </span>
          </dd>
        </dl>

        {/* Quick status change (no message) */}
        <div className="border-t border-slate-700 pt-4">
          <p className="text-xs text-slate-400 mb-2 font-medium uppercase tracking-wide">
            Change status (no message)
          </p>
          <div className="flex flex-wrap gap-2">
            {ALL_STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => handleStatusOnly(s)}
                disabled={changingStatus || s === request.status}
                className={`text-xs px-3 py-1 rounded-full border transition-colors disabled:opacity-40 ${
                  s === request.status
                    ? "border-blue-500 text-blue-300 cursor-default"
                    : "border-slate-600 text-slate-400 hover:border-blue-500 hover:text-blue-300"
                }`}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Message thread */}
      <div className="space-y-4 mb-6">
        {request.messages.map((m) => (
          <div key={m.id} className={`flex ${m.is_admin ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${
                m.is_admin
                  ? "bg-blue-700 border border-blue-600 text-white"
                  : "bg-slate-800 border border-slate-700 text-slate-100"
              }`}
            >
              <p className={`text-xs font-semibold mb-1 ${m.is_admin ? "text-blue-200" : "text-slate-400"}`}>
                {m.is_admin ? "🎧 " : "👤 "}{m.sender_name}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm">{m.message}</p>
              <p className={`text-[11px] mt-1 ${m.is_admin ? "text-blue-200" : "text-slate-500"}`}>
                {formatDateTime(m.created_at)}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Reply form */}
      {isClosed ? (
        <div className="card p-6 text-center text-slate-400 text-sm">
          This request is closed. Change the status above to reply.
        </div>
      ) : (
        <form onSubmit={handleReply} className="card p-6 space-y-4">
          <h2 className="font-semibold text-white">Reply as Support</h2>
          <textarea
            className="input min-h-[110px]"
            placeholder="Type your reply…"
            value={replyText}
            maxLength={4000}
            onChange={(e) => setReplyText(e.target.value)}
            aria-label="Admin reply"
          />

          {/* Status selector inline with reply */}
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-slate-400 whitespace-nowrap">Set status to:</label>
            <div className="flex flex-wrap gap-2">
              {ALL_STATUSES.filter((s) => s !== "closed").map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setReplyStatus(s)}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                    replyStatus === s
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-slate-600 text-slate-400 hover:border-blue-500"
                  }`}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-between items-center">
            <p className="text-xs text-slate-500">
              An email notification will be sent to the customer.
            </p>
            <button
              type="submit"
              disabled={sending || !replyText.trim()}
              className="btn-primary disabled:opacity-60"
            >
              {sending ? "Sending…" : "Send Reply"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
