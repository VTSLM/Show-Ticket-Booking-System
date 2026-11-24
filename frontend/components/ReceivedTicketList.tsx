"use client";

import { useState } from "react";
import Image from "next/image";
import Script from "next/script";
import toast from "react-hot-toast";
import { ReceivedTransfer, TRANSFER_STATUS_STYLES, transfersApi } from "@/lib/transfersApi";

export function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Tickets other people sent you. Each card carries a "Received" tag; from here you can
 * accept / decline (or pay your share first), download the PDF, and forward seats on.
 */
export default function ReceivedTicketList({
  items,
  onChanged,
  userEmail,
}: {
  items: ReceivedTransfer[];
  onChanged: () => Promise<void> | void;
  userEmail?: string | null;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [forwardingId, setForwardingId] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [recipient, setRecipient] = useState("");

  const downloadPdf = async (id: string) => {
    setBusyId(id);
    try {
      const blob = await transfersApi.pdf(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ticket_${id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Ticket PDF downloaded");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not download the ticket");
    } finally {
      setBusyId(null);
    }
  };

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
      await onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusyId(null);
    }
  };

  const checkDemoPayment = async (id: string) => {
    setBusyId(id);
    try {
      const { status } = await transfersApi.checkDemoCheckout(id);
      if (status === "awaiting_payment") toast("Waiting for Razorpay to confirm the test payment.");
      await onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not check the test payment");
      await onChanged();
    } finally {
      setBusyId(null);
    }
  };

  const startDemoPayment = async (id: string) => {
    if (!window.Razorpay) {
      toast.error("Razorpay is still loading. Try again shortly.");
      return;
    }
    setBusyId(id);
    try {
      const order = await transfersApi.demoCheckout(id);
      const checkout = new window.Razorpay({
        key: order.key_id,
        order_id: order.order_id,
        amount: order.amount,
        currency: order.currency,
        name: "TicketFlow",
        description: "Demo ticket transfer",
        prefill: { email: userEmail ?? undefined, contact: "" },
        theme: { color: "#e94560" },
        retry: { enabled: true },
        handler: async () => checkDemoPayment(id),
        modal: { ondismiss: () => { setBusyId(null); void onChanged(); } },
      });
      checkout.open();
    } catch (e) {
      setBusyId(null);
      toast.error(e instanceof Error ? e.message : "Could not open demo checkout");
    }
  };

  const openForward = (t: ReceivedTransfer) => {
    setForwardingId(t.id);
    setPicked([]);
    setRecipient("");
  };

  const togglePick = (id: string) =>
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const sendForward = async (id: string) => {
    if (picked.length === 0) return toast.error("Choose at least one seat");
    if (!recipient.trim()) return toast.error("Enter their email or phone number");
    setBusyId(id);
    try {
      const res = await transfersApi.forward(id, { seat_ids: picked, recipient: recipient.trim() });
      toast.success(res.message);
      setForwardingId(null);
      await onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not forward the tickets");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      {items.some((item) => item.demo_payment_available) && (
        <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="afterInteractive" />
      )}
      <ul className="space-y-4">
        {items.map((t) => {
          const st = TRANSFER_STATUS_STYLES[t.status] ?? { label: t.status, color: "#9ba3b5" };
          const forwardable = t.seat_items.filter((i) => !i.forward_pending);
          return (
            <li key={t.id} className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-start">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[var(--blue)] px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide text-white">
                    Received
                  </span>
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
                  {t.is_forward ? "Forwarded by" : "From"}{" "}
                  <span className="font-semibold text-white">{t.sender_name}</span> · Seats{" "}
                  <span className="font-semibold text-white">{t.seats.join(", ") || "—"}</span>
                </p>
                {t.forwarded_seats.length > 0 && (
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    ➡️ You forwarded {t.forwarded_seats.join(", ")} to someone else. Those seats are no longer on your QR.
                  </p>
                )}

                {t.status === "pending" && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {!t.requested_share_paise && (
                      <button
                        type="button"
                        className="btn-primary text-sm"
                        onClick={() => answer(t.id, true)}
                        disabled={busyId === t.id}
                      >
                        {busyId === t.id ? "Please wait…" : "Accept"}
                      </button>
                    )}
                    {t.requested_share_paise && t.demo_payment_available && (
                      <button
                        type="button"
                        className="btn-secondary text-sm"
                        disabled={busyId === t.id}
                        onClick={() => startDemoPayment(t.id)}
                      >
                        {t.demo_amount
                          ? "Resume demo checkout"
                          : `Pay ₹${(t.requested_share_paise / 100).toFixed(2)} & accept (test)`}
                      </button>
                    )}
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

                {t.status === "pending" && t.requested_share_paise && !t.demo_payment_available && (
                  <p className="mt-2 text-xs text-[var(--muted)]">Test checkout is unavailable right now.</p>
                )}
                {t.demo_amount && (
                  <div className="mt-3 text-xs text-[var(--muted)]">
                    Test payment: ₹{(t.demo_amount / 100).toFixed(2)}
                    {t.demo_refund_target && (
                      <span>
                        {" · "}
                        {t.demo_refund_target === "buyer" ? "Original buyer’s refund" : "Your refund"}: {t.demo_refund_status}
                      </span>
                    )}
                    {t.demo_payment_available && (!t.demo_refund_status || t.demo_refund_status === "pending") && (
                      <button
                        type="button"
                        className="ml-2 underline"
                        disabled={busyId === t.id}
                        onClick={() => checkDemoPayment(t.id)}
                      >
                        Check payment
                      </button>
                    )}
                  </div>
                )}

                {(t.qr_image || t.can_forward) && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {t.qr_image && (
                      <button
                        type="button"
                        className="btn-secondary text-sm"
                        onClick={() => downloadPdf(t.id)}
                        disabled={busyId === t.id}
                      >
                        {busyId === t.id ? "Please wait…" : "Download ticket PDF"}
                      </button>
                    )}
                    {t.can_forward && forwardingId !== t.id && (
                      <button type="button" className="btn-secondary text-sm" onClick={() => openForward(t)}>
                        ➡️ Forward to someone
                      </button>
                    )}
                  </div>
                )}

                {forwardingId === t.id && (
                  <div className="mt-3 space-y-3 rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-[var(--muted)]">Choose the seats to forward</p>
                    <div className="flex flex-wrap gap-2">
                      {forwardable.map((i) => {
                        const on = picked.includes(i.booking_seat_id);
                        return (
                          <button
                            key={i.booking_seat_id}
                            type="button"
                            aria-pressed={on}
                            onClick={() => togglePick(i.booking_seat_id)}
                            className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                              on
                                ? "border-[var(--blue)] bg-[var(--blue)] text-white"
                                : "border-[var(--border)] text-slate-300 hover:border-[var(--blue)]"
                            }`}
                          >
                            {i.label}
                          </button>
                        );
                      })}
                    </div>
                    <input
                      className="input w-full"
                      value={recipient}
                      onChange={(e) => setRecipient(e.target.value)}
                      placeholder="friend@example.com or 98765 43210"
                      maxLength={255}
                      autoComplete="off"
                    />
                    <p className="text-xs text-[var(--muted)]">
                      Your QR keeps working until they accept. After that, those seats move to their own QR.
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="btn-primary flex-1 text-sm"
                        disabled={busyId === t.id}
                        onClick={() => sendForward(t.id)}
                      >
                        {busyId === t.id ? "Sending…" : `Forward ${picked.length || ""} seat${picked.length === 1 ? "" : "s"}`}
                      </button>
                      <button type="button" className="btn-secondary text-sm" onClick={() => setForwardingId(null)}>
                        Close
                      </button>
                    </div>
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
    </>
  );
}
