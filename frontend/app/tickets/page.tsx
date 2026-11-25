"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { TicketsOverview, TRANSFER_STATUS_STYLES, transfersApi } from "@/lib/transfersApi";
import ReceivedTicketList, { fmtDate } from "@/components/ReceivedTicketList";

function SectionTitle({ title, hint, count }: { title: string; hint: string; count: number }) {
  return (
    <div className="mb-3 mt-8 flex flex-wrap items-baseline gap-2">
      <h2 className="text-xl font-extrabold text-white">{title}</h2>
      <span className="rounded-full border border-[var(--border)] px-2 text-xs text-[var(--muted)]">{count}</span>
      <p className="w-full text-xs text-[var(--muted)] sm:ml-2 sm:w-auto">{hint}</p>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="card p-5 text-sm text-[var(--muted)]">{text}</div>;
}

/** All your tickets in one place: Available (still yours), Split (sent to others), Received (sent to you). */
export default function TicketsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<TicketsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await transfersApi.overview());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load your tickets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/auth/login?redirect=%2Ftickets");
      return;
    }
    load();
  }, [authLoading, user, router, load]);

  const cancel = async (id: string) => {
    setBusyId(id);
    try {
      await transfersApi.cancel(id);
      toast.success("Transfer cancelled. The seats are back with you.");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not cancel the transfer");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <p className="mb-2 text-xs font-bold uppercase tracking-widest text-[var(--blue)]">Your tickets</p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Tickets</h1>
        <Link href="/bookings" className="btn-secondary text-sm">
          My Bookings
        </Link>
      </div>

      {loading || !data ? (
        <p className="mt-6 text-[var(--muted)]">Loading…</p>
      ) : (
        <>
          <SectionTitle title="Available" count={data.available.length} hint="Seats still with you. Open one to split or send it." />
          {data.available.length === 0 ? (
            <Empty text="No upcoming seats with you right now." />
          ) : (
            <ul className="space-y-3">
              {data.available.map((b) => (
                <li key={b.booking_id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <p className="font-bold text-white">{b.event_title}</p>
                    <p className="text-sm text-[var(--muted)]">
                      {fmtDate(b.start_time)} · {b.venue_name}, {b.city}
                    </p>
                    <p className="mt-1 text-sm text-slate-300">
                      Seats <span className="font-semibold text-white">{b.seats.join(", ")}</span>
                      {b.pending_count > 0 && (
                        <span className="ml-2 text-xs text-[var(--muted)]">({b.pending_count} waiting for a reply)</span>
                      )}
                    </p>
                  </div>
                  <Link href={`/bookings/${b.booking_id}`} className="btn-primary px-3 py-1 text-xs">
                    Split / Transfer
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <SectionTitle title="Split" count={data.split.length} hint="Tickets you sent or forwarded to other people." />
          {data.split.length === 0 ? (
            <Empty text="You haven't sent any tickets to anyone yet." />
          ) : (
            <ul className="space-y-3">
              {data.split.map((t) => {
                const st = TRANSFER_STATUS_STYLES[t.status] ?? { label: t.status, color: "#9ba3b5" };
                return (
                  <li key={t.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-bold text-white">{t.event_title}</p>
                        {t.is_forward && (
                          <span className="rounded-full border border-[var(--border)] px-2 text-[10px] font-bold uppercase text-[var(--muted)]">
                            Forwarded
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-[var(--muted)]">{fmtDate(t.start_time)} · {t.venue_name}, {t.city}</p>
                      <p className="mt-1 text-sm text-slate-300">
                        <span className="font-semibold text-white">{t.seats.join(", ")}</span> → {t.recipient_name}
                        <span className="ml-2 text-xs font-semibold" style={{ color: st.color }}>
                          {t.used ? "Used at venue" : st.label}
                        </span>
                      </p>
                    </div>
                    {t.status === "pending" && (
                      <button
                        type="button"
                        className="text-xs text-[var(--muted)] underline hover:text-white"
                        disabled={busyId === t.id}
                        onClick={() => cancel(t.id)}
                      >
                        {busyId === t.id ? "Cancelling…" : "Cancel"}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          <SectionTitle title="Received" count={data.received.length} hint="Tickets other people sent to you. You can forward them on." />
          {data.received.length === 0 ? (
            <Empty text="Nothing received yet. When someone sends you seats, they show up here." />
          ) : (
            <ReceivedTicketList items={data.received} onChanged={load} userEmail={user?.email} />
          )}
        </>
      )}
    </div>
  );
}
