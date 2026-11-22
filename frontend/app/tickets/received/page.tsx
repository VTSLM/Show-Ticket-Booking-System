"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { ReceivedTransfer, TRANSFER_STATUS_STYLES, transfersApi } from "@/lib/transfersApi";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReceivedTicketsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<ReceivedTransfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await transfersApi.received());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load your tickets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/auth/login");
      return;
    }
    load();
  }, [authLoading, user, router, load]);

  const answer = async (id: string, accept: boolean) => {
    setBusyId(id);
    try {
      if (accept) {
        await transfersApi.accept(id);
        toast.success("Tickets accepted. Show the QR code at the venue.");
      } else {
        await transfersApi.decline(id);
        toast.success("Tickets declined");
      }
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <p className="mb-2 text-xs font-bold uppercase tracking-widest text-[var(--blue)]">From friends</p>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Received tickets</h1>
        <Link href="/bookings" className="btn-secondary text-sm">
          ← My Bookings
        </Link>
      </div>

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-lg font-semibold text-white">No tickets yet</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            When someone sends you seats from their booking, they will show up here.
          </p>
        </div>
      ) : (
        <ul className="space-y-4">
          {items.map((t) => {
            const st = TRANSFER_STATUS_STYLES[t.status] ?? { label: t.status, color: "#9ba3b5" };
            return (
              <li key={t.id} className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-start">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-bold text-white">{t.event_title}</h2>
                    <span
                      className="rounded-full px-3 py-0.5 text-xs font-bold"
                      style={{ color: st.color, background: `${st.color}22` }}
                    >
                      {t.used ? "Used at venue" : st.label}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    {fmtDate(t.start_time)} · {t.venue_name}, {t.city} · {t.screen_name}
                  </p>
                  <p className="mt-2 text-sm text-slate-300">
                    From <span className="font-semibold text-white">{t.sender_name}</span> · Seats{" "}
                    <span className="font-semibold text-white">{t.seats.join(", ")}</span>
                  </p>

                  {t.status === "pending" && (
                    <div className="mt-4 flex gap-2">
                      <button
                        type="button"
                        className="btn-primary text-sm"
                        onClick={() => answer(t.id, true)}
                        disabled={busyId === t.id}
                      >
                        {busyId === t.id ? "Please wait…" : "Accept"}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary text-sm"
                        onClick={() => answer(t.id, false)}
                        disabled={busyId === t.id}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                </div>

                {t.qr_image && (
                  <div className="flex flex-col items-center gap-1 self-center rounded-lg bg-white p-2">
                    <Image
                      src={`data:image/png;base64,${t.qr_image}`}
                      alt={`Entry QR code for seats ${t.seats.join(", ")}`}
                      width={140}
                      height={140}
                      unoptimized
                    />
                    <span className="text-[10px] font-semibold text-slate-700">Show this at entry</span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
