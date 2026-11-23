"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { BookingTransfers, TRANSFER_STATUS_STYLES, transfersApi } from "@/lib/transfersApi";

/** "Send to a friend" box on a confirmed booking: pick seats, enter email or phone, track transfers. */
export default function TransferTicketsPanel({ bookingId }: { bookingId: string }) {
  const [data, setData] = useState<BookingTransfers | null>(null);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [zoneQuantities, setZoneQuantities] = useState<Record<string, number>>({});
  const [recipient, setRecipient] = useState("");
  const [sending, setSending] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await transfersApi.forBooking(bookingId));
    } catch {
      setData(null); // panel just stays hidden if this fails
    }
  }, [bookingId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!data || (data.seats.length === 0 && data.zones.length === 0 && data.transfers.length === 0)) return null;

  const yours = data.seats.filter((s) => s.state === "yours");
  const toggle = (id: string) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const send = async () => {
    const zones = Object.entries(zoneQuantities).filter(([, quantity]) => quantity > 0).map(([booking_zone_id, quantity]) => ({ booking_zone_id, quantity }));
    if (selected.length === 0 && zones.length === 0) return toast.error("Choose at least one ticket");
    if (!recipient.trim()) return toast.error("Enter their email or phone number");
    setSending(true);
    try {
      const res = await transfersApi.send({ booking_id: bookingId, seat_ids: selected, zones, recipient: recipient.trim() });
      toast.success(res.message);
      setSelected([]);
      setZoneQuantities({});
      setRecipient("");
      setOpen(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not send the tickets");
    } finally {
      setSending(false);
    }
  };

  const cancel = async (id: string) => {
    setBusyId(id);
    try {
      await transfersApi.cancel(id);
      toast.success("Transfer cancelled. The seats are back on your booking.");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not cancel the transfer");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold text-white">Send tickets to a friend</p>
        {data.can_transfer && !open && (
          <button type="button" className="btn-primary px-3 py-1 text-xs" onClick={() => setOpen(true)}>
            Split / Transfer
          </button>
        )}
      </div>

      {!data.can_transfer && data.reason && (
        <p className="mt-2 text-xs text-[var(--muted)]">{data.reason}</p>
      )}

      {open && data.can_transfer && (
        <div className="mt-3 space-y-3">
          <div>
            <p className="mb-2 text-xs text-[var(--muted)]">Choose the seats to send</p>
            <div className="flex flex-wrap gap-2">
              {yours.map((s) => {
                const on = selected.includes(s.booking_seat_id);
                return (
                  <button
                    key={s.booking_seat_id}
                    type="button"
                    onClick={() => toggle(s.booking_seat_id)}
                    aria-pressed={on}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                      on
                        ? "border-[var(--blue)] bg-[var(--blue)] text-white"
                        : "border-[var(--border)] text-slate-300 hover:border-[var(--blue)]"
                    }`}
                  >
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>
          {data.zones.filter((z) => z.available > 0).map((z) => (
            <label key={z.booking_zone_id} className="block text-slate-300">
              {z.name} ({z.available} available)
              <input type="number" min={0} max={z.available} value={zoneQuantities[z.booking_zone_id] || 0}
                onChange={(e) => setZoneQuantities((cur) => ({ ...cur, [z.booking_zone_id]: Math.min(z.available, Math.max(0, Math.floor(Number(e.target.value) || 0))) }))}
                className="input ml-3 w-20" />
            </label>
          ))}
          <label className="block">
            <span className="mb-1 block text-xs text-[var(--muted)]">Their email or mobile number</span>
            <input
              className="input w-full"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="friend@example.com or 98765 43210"
              maxLength={255}
              autoComplete="off"
            />
          </label>
          <p className="text-xs text-[var(--muted)]">
            If they don&apos;t have an account yet, send to their email and they can sign up and verify it.
            Once they accept, those seats get their own QR code and your QR stops working for them.
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn-primary flex-1 text-sm" onClick={send} disabled={sending}>
              {sending ? "Sending…" : "Send tickets"}
            </button>
            <button type="button" className="btn-secondary text-sm" onClick={() => setOpen(false)} disabled={sending}>
              Close
            </button>
          </div>
        </div>
      )}

      {data.transfers.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-[var(--border)] pt-3">
          {data.transfers.map((t) => {
            const st = TRANSFER_STATUS_STYLES[t.status] ?? { label: t.status, color: "#9ba3b5" };
            return (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-slate-300">
                  <span className="font-semibold text-white">{t.seats.join(", ")}</span> → {t.recipient_name}
                  <span className="ml-2 text-xs font-semibold" style={{ color: st.color }}>
                    {t.used ? "Used at venue" : st.label}
                  </span>
                </span>
                {t.status === "pending" && (
                  <button
                    type="button"
                    className="text-xs text-[var(--muted)] underline hover:text-white"
                    onClick={() => cancel(t.id)}
                    disabled={busyId === t.id}
                  >
                    {busyId === t.id ? "Cancelling…" : "Cancel"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
