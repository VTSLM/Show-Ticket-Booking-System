import React from "react";
import Link from "next/link";
import { ShowItem } from "../lib/types";

interface ShowListProps {
  shows: ShowItem[];
  loading: boolean;
  onOpenCreateShow: () => void;
}

export default function ShowList({ shows, loading, onOpenCreateShow }: ShowListProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="cinema-device-frame h-[520px] animate-pulse bg-slate-900/40" />
        ))}
      </div>
    );
  }

  if (shows.length === 0) {
    return (
      <div className="cinema-device-frame mx-auto max-w-xl p-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-amber-500/20 text-3xl shadow-[0_0_25px_rgba(245,158,11,0.25)]">
          🎟️
        </div>
        <h3 className="mt-5 text-xl font-bold text-white">No Scheduled Showtimes</h3>
        <p className="mt-2 text-sm text-slate-400">
          Schedule showtimes across your screens and hand them off to seat category pricing.
        </p>
        <div className="mt-6">
          <button
            onClick={onOpenCreateShow}
            className="rounded-2xl bg-blue-600 px-6 py-3 text-xs font-bold text-white shadow-glow hover:bg-blue-500 transition-all"
          >
            + Schedule First Show
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      {shows.map((show) => {
        const start = new Date(show.start_time);
        const end = new Date(show.end_time);

        const dateStr = start.toLocaleDateString(undefined, {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
        });

        const timeStr = `${start.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })}`;

        const pricingUrl = `/pricing?show_id=${show.id}&event_id=${show.event_id}&screen_id=${show.screen_id}&seat_count=${show.seat_count || 0}`;

        return (
          <div
            key={show.id}
            className="cinema-device-frame group relative flex flex-col overflow-hidden transition-all duration-300 hover:scale-[1.01] hover:shadow-glow"
          >
            {/* Top Cinema Backdrop Banner */}
            <div className="relative aspect-[16/9] w-full overflow-hidden bg-slate-950">
              {show.event_poster_url ? (
                <img
                  src={show.event_poster_url}
                  alt={show.event_title || "Show"}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=800&auto=format&fit=crop";
                  }}
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-gradient-to-tr from-blue-950/70 to-slate-900">
                  <span className="text-3xl">🎞️</span>
                </div>
              )}

              {/* Gradient Overlay */}
              <div className="absolute inset-0 poster-gradient-overlay" />

              {/* Category Badge on top */}
              <div className="absolute top-4 left-4 right-4 flex items-center justify-between">
                <span className="rounded-xl border border-white/20 bg-black/70 px-2.5 py-1 text-[11px] font-black uppercase tracking-wider text-white backdrop-blur-md">
                  {show.event_type || "MOVIE"}
                </span>

                <span className="rounded-xl border border-blue-400/40 bg-blue-900/80 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-blue-200 backdrop-blur-md">
                  {show.status}
                </span>
              </div>
            </div>

            {/* Show Details Section matching Left Screen Reference */}
            <div className="flex flex-1 flex-col p-6 -mt-6 relative z-10">
              <h3 className="text-2xl font-black text-white tracking-tight line-clamp-1 group-hover:text-blue-400 transition-colors">
                {show.event_title || "Show"}
              </h3>

              {/* Badges row: [7+], [ENG], [4DX Dolby Atmos] */}
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <span className="rounded-lg border border-slate-700 bg-slate-900/90 px-2 py-0.5 text-[11px] font-bold text-slate-300">
                  U/A
                </span>
                <span className="rounded-lg border border-slate-700 bg-slate-900/90 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-300">
                  ENG
                </span>
                <span className="rounded-lg border border-blue-500/40 bg-blue-950/50 px-2 py-0.5 text-[11px] font-bold text-blue-300">
                  4DX Dolby Atmos
                </span>
              </div>

              {/* Metadata Grid matching reference: Cinema, Date, Time */}
              <div className="mt-5 grid grid-cols-3 gap-3 rounded-2xl border border-slate-800 bg-[#0d1326] p-3.5">
                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                    Cinema
                  </span>
                  <p className="mt-1 font-bold text-white text-xs truncate">
                    {show.venue_name || "Mall of Tripla"}
                  </p>
                </div>

                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                    Date
                  </span>
                  <p className="mt-1 font-bold text-white text-xs">
                    {dateStr}
                  </p>
                </div>

                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                    Time
                  </span>
                  <p className="mt-1 font-bold text-blue-400 text-xs">
                    {timeStr}
                  </p>
                </div>
              </div>

              {/* Hall / Screen & Physical Capacity */}
              <div className="mt-4 flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 text-slate-300">
                  <span className="font-semibold text-slate-400">Screen:</span>
                  <span className="font-bold text-white">{show.screen_name || "Screen 1"}</span>
                </div>

                <div className="rounded-xl border border-blue-500/30 bg-blue-950/40 px-2.5 py-1 text-xs font-semibold text-blue-200">
                  🪑 {show.seat_count || "—"} seats
                </div>
              </div>

              {/* Perforated ticket tear line with side punch notches */}
              <div className="my-5 ticket-tear relative" />

              {/* Pricing readiness status and handoff button */}
              <div className="mt-auto space-y-3">
                <div className="text-center">
                  {show.pricing_ready ? (
                    <span className="inline-block text-[11px] font-bold text-emerald-400">
                      ✓ Pricing Configured (Public Booking Ready)
                    </span>
                  ) : (
                    <span className="inline-block text-[11px] font-bold text-amber-400">
                      ⏳ Pending Seat Pricing (Feature 04)
                    </span>
                  )}
                </div>

                <Link
                  href={pricingUrl}
                  className="block w-full rounded-2xl bg-blue-600 py-3.5 text-center text-xs font-bold text-white shadow-glow hover:bg-blue-500 hover:scale-[1.02] active:scale-[0.98] transition-all"
                >
                  Continue to Seat Selection & Pricing →
                </Link>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
