import React from "react";
import { EventItem, ShowItem, VenueItem } from "../lib/types";

interface StatsBarProps {
  events: EventItem[];
  shows: ShowItem[];
  venues: VenueItem[];
}

export default function StatsBar({ events, shows, venues }: StatsBarProps) {
  const publishedEvents = events.filter((e) => e.status === "published").length;
  const pendingPricingShows = shows.filter((s) => !s.pricing_ready).length;
  const totalScreens = venues.reduce((acc, v) => acc + (v.screens?.length || 0), 0);

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {/* Total Events */}
      <div className="cinema-glass-card p-5">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Catalogue Events</p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-black tracking-tight text-white">{events.length}</span>
          <span className="text-xs font-medium text-slate-400">
            ({publishedEvents} live)
          </span>
        </div>
      </div>

      {/* Scheduled Shows */}
      <div className="cinema-glass-card p-5">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Scheduled Shows</p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-black tracking-tight text-blue-400">{shows.length}</span>
          <span className="text-xs font-medium text-slate-400">sessions</span>
        </div>
      </div>

      {/* Screens */}
      <div className="cinema-glass-card p-5">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Auditorium Screens</p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-black tracking-tight text-white">{totalScreens}</span>
          <span className="text-xs font-medium text-slate-400">across {venues.length} cinemas</span>
        </div>
      </div>

      {/* Pending Pricing Handoff */}
      <div className="cinema-glass-card p-5 border-amber-500/30">
        <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Pending Seat Pricing</p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-3xl font-black tracking-tight text-amber-300">
            {pendingPricingShows}
          </span>
          <span className="text-xs font-medium text-amber-400/80">awaiting tiering</span>
        </div>
      </div>
    </div>
  );
}
