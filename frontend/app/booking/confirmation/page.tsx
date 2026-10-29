"use client";

import { useEffect, useState } from "react";
import TicketCard from "@/components/ticket/TicketCard";
import { BookingConfirmation } from "@/types/booking";

const BASE_PAYLOAD = {
  booking_id: "BKG-20260928-00142",
  transaction_id: "TXN-RAZ-9983721",
  user: {
    user_id: "USR-4421",
    name: "Hari Sharma",
    // email is filled in dynamically from the form
  },
  event: {
    event_id: "EVT-881",
    name: "Coldplay - Music of the Spheres",
    date: "2026-11-15",
    time: "19:30",
    venue: "Narendra Modi Stadium, Ahmedabad",
  },
  seats: [
    { seat_id: "S-A14", row: "A", number: 14, tier: "Premium", price: 4500 },
  ],
  total_amount: 4500,
  payment_status: "SUCCESS",
  booked_at: "2026-09-28T18:45:00Z",
};

type Step = "input" | "loading" | "done";

export default function ConfirmationPage() {
  const [step, setStep] = useState<Step>("input");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [ticket, setTicket] = useState<BookingConfirmation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStep("loading");
    setError(null);

    try {
      const payload = {
        ...BASE_PAYLOAD,
        user: { ...BASE_PAYLOAD.user, email: recipientEmail },
      };

      const res = await fetch("http://localhost:8000/bookings/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      setTicket(data);
      setStep("done");
    } catch (err) {
      setError((err as Error).message);
      setStep("input");
    }
  };

  const handleDownload = async () => {
    if (!ticket) return;
    const res = await fetch(`http://localhost:8000${ticket.pdf_download_url}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ticket_${ticket.booking_id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Step 1: Email input ──────────────────────────────────────────────────
  if (step === "input") {
    return (
      <main className="min-h-screen bg-[#0D0D0F] flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-blue-900/30 border border-blue-800 mb-4">
              <svg className="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-white text-2xl font-bold">Enter your email</h1>
            <p className="text-slate-400 text-sm mt-1">
              Your ticket will be sent to this address
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <input
              type="email"
              required
              value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500
                         rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500
                         focus:ring-1 focus:ring-blue-500 transition"
            />

            {error && (
              <p className="text-red-400 text-xs text-center">{error}</p>
            )}

            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 active:scale-95 transition-all
                         text-white font-semibold py-3 rounded-xl text-sm"
            >
              Confirm Booking & Send Ticket
            </button>
          </form>

          <p className="text-slate-600 text-xs text-center mt-4">
            Email will be sent from hs9998706@gmail.com
          </p>
        </div>
      </main>
    );
  }

  // ── Step 2: Loading ──────────────────────────────────────────────────────
  if (step === "loading") {
    return (
      <main className="min-h-screen bg-[#0D0D0F] flex flex-col items-center justify-center gap-4">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Generating your ticket…</p>
      </main>
    );
  }

  // ── Step 3: Error (shouldn't normally reach here but safety net) ─────────
  if (!ticket) {
    return (
      <main className="min-h-screen bg-[#0D0D0F] flex flex-col items-center justify-center gap-4 px-4">
        <div className="w-16 h-16 rounded-full bg-red-900/30 flex items-center justify-center">
          <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 className="text-white text-xl font-semibold">Something went wrong</h2>
        <p className="text-slate-400 text-sm text-center max-w-sm">{error}</p>
        <button
          onClick={() => setStep("input")}
          className="text-blue-400 text-sm underline mt-2"
        >
          Try again
        </button>
      </main>
    );
  }

  // ── Step 4: Done ─────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-[#0D0D0F] px-4 py-10">
      <div className="max-w-lg mx-auto mb-8 text-center">
        <div className="inline-flex items-center gap-2 bg-green-900/30 border border-green-800 text-green-400 rounded-full px-4 py-1.5 text-sm font-medium mb-4">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          Booking Confirmed
        </div>
        <h1 className="text-white text-2xl font-bold">You&apos;re going! 🎉</h1>
        <p className="text-slate-400 text-sm mt-1">
          {ticket.email_sent
            ? `Ticket sent to ${ticket.user.email}`
            : "Ticket ready below · Email delivery failed (check logs)"}
        </p>
      </div>
      <TicketCard data={ticket} />
      <div className="max-w-lg mx-auto mt-6 flex gap-3">
        <button
          onClick={handleDownload}
          className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 transition-all text-white font-semibold py-3 rounded-xl text-sm"
        >
          Download PDF
        </button>
        <button
          onClick={() => window.location.href = "/"}
          className="flex-1 flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 active:scale-95 transition-all text-slate-200 font-semibold py-3 rounded-xl text-sm"
        >
          Browse More Events
        </button>
      </div>
      <div className="max-w-lg mx-auto mt-4 text-center">
        <p className="text-slate-600 text-[11px] font-mono">TXN: {ticket.transaction_id}</p>
      </div>
    </main>
  );
}
