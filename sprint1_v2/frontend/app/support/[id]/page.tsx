"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  supportApi,
  SupportRequestDetail,
  CATEGORY_LABELS,
  STATUS_LABELS,
  STATUS_STYLES,
  formatDateTime,
} from "@/lib/supportApi";

export default function SupportRequestPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [request, setRequest] = useState<SupportRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    return supportApi
      .get(id)
      .then(setRequest)
      .catch(() => setRequest(null))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    if (user && id) load();
  }, [user, authLoading, id, router, load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [request?.messages.length]);

  if (loading || authLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>;
  if (!request) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">Support request not found.</p>
        <Link href="/support" className="btn-secondary">My Requests</Link>
      </div>
    );
  }

  const isResolved = request.status === "resolved";
  const isClosed = request.status === "closed";
  const canReply = !isResolved && !isClosed;

  const handleSend = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const text = reply.trim();
    if (!text) return;
    setSending(true);
    try {
      if (isResolved) {
        await supportApi.reopen(request.id, text);
        toast.success("Request reopened. Our team will take another look.");
      } else {
        await supportApi.reply(request.id, text);
      }
      setReply("");
      await load();
    } catch (err: any) {
      toast.error(err.message || "Could not send your message");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Link href="/support" className="text-sm text-slate-400 hover:text-blue-400">← My Requests</Link>

      <div className="card p-6 mt-2 mb-6">
        <div className="flex justify-between items-start gap-4">
          <div className="min-w-0">
            <p className="text-xs text-slate-500 font-mono">{request.request_number}</p>
            <h1 className="text-2xl font-bold text-white break-words">{request.subject}</h1>
          </div>
          <span className={`text-xs px-3 py-1 rounded-full font-semibold whitespace-nowrap ${STATUS_STYLES[request.status]}`}>
            {STATUS_LABELS[request.status]}
          </span>
        </div>
        <dl className="grid grid-cols-2 gap-2 text-sm mt-4">
          <dt className="text-slate-400">Category</dt>
          <dd>{CATEGORY_LABELS[request.category]}</dd>
          {request.booking_id && (
            <>
              <dt className="text-slate-400">Booking</dt>
              <dd>
                <Link href={`/bookings/${request.booking_id}`} className="text-blue-400 hover:underline">
                  {request.booking_number || "View booking"}
                </Link>
              </dd>
            </>
          )}
          <dt className="text-slate-400">Opened</dt>
          <dd>{formatDateTime(request.created_at)}</dd>
        </dl>
      </div>

      <div className="space-y-4 mb-6">
        {request.messages.map(m => (
          <div key={m.id} className={`flex ${m.is_admin ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${
                m.is_admin ? "bg-slate-800 border border-slate-700 text-slate-100" : "bg-blue-600 text-white"
              }`}
            >
              <p className={`text-xs font-semibold mb-1 ${m.is_admin ? "text-blue-300" : "text-blue-100"}`}>
                {m.is_admin ? "🎧 " : ""}{m.sender_name}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm">{m.message}</p>
              <p className={`text-[11px] mt-1 ${m.is_admin ? "text-slate-400" : "text-blue-100"}`}>
                {formatDateTime(m.created_at)}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {isClosed ? (
        <div className="card p-6 text-center text-slate-400 text-sm">
          This request is closed. If you still need help,{" "}
          <Link href="/support/new" className="text-blue-400 hover:underline">raise a new request</Link>.
        </div>
      ) : (
        <form onSubmit={handleSend} className="card p-6 space-y-3">
          {isResolved && (
            <p className="text-sm text-green-300 bg-green-500/10 border border-green-500/30 rounded-lg p-3">
              ✅ Our team marked this as resolved. Not fixed? Tell us why below to reopen it.
            </p>
          )}
          <textarea
            className="input min-h-[90px]"
            placeholder={canReply ? "Write a reply..." : "What's still not working?"}
            value={reply}
            maxLength={2000}
            onChange={e => setReply(e.target.value)}
            aria-label="Your message"
          />
          <div className="flex justify-end">
            <button type="submit" disabled={sending || !reply.trim()} className="btn-primary disabled:opacity-60">
              {sending ? "Sending..." : isResolved ? "Reopen Request" : "Send"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
