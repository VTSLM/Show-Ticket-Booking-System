"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { fetchShowHandoff } from "../../lib/api";
import { ShowHandoffData } from "../../lib/types";

function PricingTicketContent() {
  const searchParams = useSearchParams();
  const showId = searchParams.get("show_id");
  const eventIdParam = searchParams.get("event_id");
  const screenIdParam = searchParams.get("screen_id");
  const seatCountParam = searchParams.get("seat_count");

  const [handoff, setHandoff] = useState<ShowHandoffData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    if (showId) {
      setLoading(true);
      fetchShowHandoff(showId)
        .then((data) => setHandoff(data))
        .catch(() => setHandoff(null))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [showId]);

  const dateObj = handoff ? new Date(handoff.start_time) : new Date();
  const dateFormatted = `${String(dateObj.getDate()).padStart(2, "0")}.${String(dateObj.getMonth() + 1).padStart(2, "0")}.`;
  const timeFormatted = `${String(dateObj.getHours()).padStart(2, "0")}:${String(dateObj.getMinutes()).padStart(2, "0")}`;

  return (
    <div className="min-h-screen bg-[#050711] text-slate-100 p-4 sm:p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-md space-y-6">
        {/* Top Back Nav matching reference */}
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
          >
            <span className="text-base">‹</span> Back to Manager Dashboard
          </Link>

          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
            Feature 04 Handoff
          </span>
        </div>

        {/* The Phone/Ticket Frame matching the right screen in reference */}
        <div className="cinema-device-frame overflow-hidden shadow-glow">
          {/* Top Dark Header */}
          <div className="p-6 pb-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                My Tickets & Shows
              </span>
              <button
                onClick={() => setShowJson(!showJson)}
                className="rounded-lg border border-blue-500/40 bg-blue-950/60 px-2 py-0.5 text-[11px] font-bold text-blue-300 hover:bg-blue-900/60"
              >
                {showJson ? "View Ticket" : "View JSON Payload"}
              </button>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <h2 className="text-2xl font-black text-white tracking-tight">
                {handoff?.event_title || "Sonic The Hedgehog 2"}
              </h2>
              <span className="text-slate-400 text-sm">↗</span>
            </div>

            {/* Badges: [7+], [ENG], [4DX Dolby Atmos] */}
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <span className="rounded-md border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[10px] font-bold text-slate-300">
                7+
              </span>
              <span className="rounded-md border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-300">
                ENG
              </span>
              <span className="rounded-md border border-blue-500/40 bg-blue-950/50 px-2 py-0.5 text-[10px] font-bold text-blue-300">
                4DX Dolby Atmos
              </span>
            </div>
          </div>

          {/* Location Bar with Backdrop image */}
          <div className="relative overflow-hidden bg-slate-900 px-6 py-4">
            <div className="relative z-10 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold text-white flex items-center gap-1">
                  {handoff?.venue_name || "Mall of Tripla"} <span className="text-[10px] text-blue-400">▾</span>
                </p>
                <p className="text-[11px] text-slate-400 font-medium">
                  {handoff?.screen_name || "Screen 1"} • Fredrikanterassi 1, Helsinki
                </p>
              </div>
            </div>
          </div>

          {!showJson ? (
            <>
              {/* Timing & Seating Grid matching right screen */}
              <div className="bg-[#090d1a] px-6 py-5">
                <div className="grid grid-cols-2 gap-4 border-b border-slate-800 pb-4">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Date
                    </span>
                    <p className="mt-1 text-2xl font-black text-white">
                      {dateFormatted}
                    </p>
                  </div>

                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Time
                    </span>
                    <p className="mt-1 text-2xl font-black text-white">
                      {timeFormatted}
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-xl bg-[#0d1326] p-2.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Hall
                    </span>
                    <p className="mt-1 text-base font-black text-white">
                      {handoff?.screen_name?.replace(/[^0-9]/g, "") || "5"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#0d1326] p-2.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Capacity
                    </span>
                    <p className="mt-1 text-base font-black text-blue-400">
                      {handoff?.seat_count ?? seatCountParam ?? "120"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#0d1326] p-2.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Status
                    </span>
                    <p className="mt-1 text-xs font-black text-amber-400 uppercase">
                      Unpriced
                    </p>
                  </div>
                </div>
              </div>

              {/* Dotted Perforated Ticket Divider with side punch notches */}
              <div className="ticket-tear my-2" />

              {/* White Ticket Stub Section with QR Code matching right screen */}
              <div className="bg-white p-6 pt-5 text-center text-slate-900 rounded-b-[30px]">
                {/* SVG QR Code Simulation */}
                <div className="mx-auto flex h-36 w-36 items-center justify-center rounded-2xl border-2 border-slate-900 p-2">
                  <svg className="h-full w-full" viewBox="0 0 100 100" fill="none">
                    {/* Corner Position Detection Squares */}
                    <rect x="5" y="5" width="26" height="26" rx="4" fill="#090d1a" />
                    <rect x="9" y="9" width="18" height="18" rx="2" fill="white" />
                    <rect x="13" y="13" width="10" height="10" fill="#090d1a" />

                    <rect x="69" y="5" width="26" height="26" rx="4" fill="#090d1a" />
                    <rect x="73" y="9" width="18" height="18" rx="2" fill="white" />
                    <rect x="77" y="13" width="10" height="10" fill="#090d1a" />

                    <rect x="5" y="69" width="26" height="26" rx="4" fill="#090d1a" />
                    <rect x="9" y="73" width="18" height="18" rx="2" fill="white" />
                    <rect x="13" y="77" width="10" height="10" fill="#090d1a" />

                    {/* QR Pixel matrix patterns */}
                    <rect x="36" y="8" width="6" height="6" fill="#090d1a" />
                    <rect x="46" y="8" width="6" height="6" fill="#090d1a" />
                    <rect x="56" y="8" width="6" height="6" fill="#090d1a" />

                    <rect x="36" y="20" width="6" height="6" fill="#090d1a" />
                    <rect x="50" y="20" width="12" height="6" fill="#090d1a" />

                    <rect x="8" y="40" width="14" height="6" fill="#090d1a" />
                    <rect x="28" y="40" width="8" height="6" fill="#090d1a" />
                    <rect x="40" y="36" width="6" height="12" fill="#090d1a" />
                    <rect x="52" y="38" width="14" height="6" fill="#090d1a" />
                    <rect x="72" y="40" width="20" height="6" fill="#090d1a" />

                    <rect x="10" y="52" width="20" height="6" fill="#090d1a" />
                    <rect x="36" y="52" width="12" height="6" fill="#090d1a" />
                    <rect x="54" y="50" width="8" height="8" fill="#090d1a" />
                    <rect x="68" y="52" width="10" height="6" fill="#090d1a" />
                    <rect x="82" y="52" width="10" height="6" fill="#090d1a" />

                    <rect x="36" y="68" width="8" height="8" fill="#090d1a" />
                    <rect x="48" y="72" width="14" height="6" fill="#090d1a" />
                    <rect x="68" y="68" width="12" height="8" fill="#090d1a" />
                    <rect x="84" y="72" width="8" height="8" fill="#090d1a" />

                    <rect x="36" y="84" width="18" height="6" fill="#090d1a" />
                    <rect x="60" y="82" width="8" height="8" fill="#090d1a" />
                    <rect x="74" y="84" width="18" height="6" fill="#090d1a" />
                  </svg>
                </div>

                <p className="mt-4 text-[11px] font-bold text-slate-800 leading-snug">
                  Feature 04 Integration Contract — Teammate Handoff Stub
                </p>
                <p className="mt-1 text-[10px] text-slate-500 font-medium">
                  Show ID: {handoff?.show_id || showId || "sh-uuid"} • Verified Capacity: {handoff?.seat_count ?? seatCountParam ?? "—"} seats
                </p>
              </div>
            </>
          ) : (
            <div className="bg-[#090d1a] p-6 rounded-b-[30px] space-y-3">
              <span className="text-xs font-bold text-blue-400">API Contract JSON</span>
              <pre className="rounded-xl bg-black p-3.5 font-mono text-[11px] text-blue-300 overflow-x-auto border border-blue-900/40">
                {JSON.stringify(
                  handoff || {
                    show_id: showId,
                    event_id: eventIdParam,
                    screen_id: screenIdParam,
                    seat_count: Number(seatCountParam) || 0,
                    pricing_ready: false,
                    pricing_route: `/pricing?show_id=${showId}&event_id=${eventIdParam}&screen_id=${screenIdParam}&seat_count=${seatCountParam}`,
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          )}
        </div>

        {/* Safeguard Alert Notice */}
        <div className="rounded-2xl border border-amber-500/40 bg-amber-950/30 p-4 text-xs text-amber-200">
          <p className="font-bold flex items-center gap-2">
            <span>🔒</span> Show Publication Safeguard: UNPUBLISHED
          </p>
          <p className="mt-1 text-amber-300/80 leading-relaxed">
            Per the requirements, this show cannot be booked by customers until your teammate configures seat category pricing (VIP, Premium, Standard) and generates priced <code>show_seats</code> records.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="p-8 text-white text-center">Loading cinema ticket handoff...</div>}>
      <PricingTicketContent />
    </Suspense>
  );
}
