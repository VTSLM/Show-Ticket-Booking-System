import React from "react";
import { EventItem } from "../lib/types";

interface EventListProps {
  events: EventItem[];
  loading: boolean;
  onSelectEventForShow: (eventId: string) => void;
  onOpenCreateEvent: () => void;
  onDeleteEvent?: (eventId: string) => void;
}

export default function EventList({
  events,
  loading,
  onSelectEventForShow,
  onOpenCreateEvent,
  onDeleteEvent,
}: EventListProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="cinema-device-frame h-[520px] animate-pulse bg-slate-900/40" />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="cinema-device-frame mx-auto max-w-xl p-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-blue-600/20 text-3xl shadow-glow">
          🎬
        </div>
        <h3 className="mt-5 text-xl font-bold text-white">No Movies or Events Listed</h3>
        <p className="mt-2 text-sm text-slate-400">
          Add your first movie, concert, or performance to schedule cinema showtimes.
        </p>
        <div className="mt-6">
          <button
            onClick={onOpenCreateEvent}
            className="rounded-2xl bg-blue-600 px-6 py-3 text-xs font-bold text-white shadow-glow hover:bg-blue-500 transition-all"
          >
            + Create New Event
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      {events.map((event) => {
        return (
          <div
            key={event.id}
            className="cinema-device-frame group relative flex flex-col overflow-hidden transition-all duration-300 hover:scale-[1.01] hover:shadow-glow"
          >
            {/* Top Poster Hero Section with Gradient Overlay */}
            <div className="relative aspect-[16/11] w-full overflow-hidden bg-slate-950">
              {event.poster_url ? (
                <img
                  src={event.poster_url}
                  alt={event.title}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      "https://images.unsplash.com/photo-1536440136628-849c177e76a1?q=80&w=800&auto=format&fit=crop";
                  }}
                />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-b from-blue-950/40 to-[#090d1a] p-6 text-center">
                  <span className="text-4xl">🍿</span>
                  <span className="mt-2 text-xs font-semibold text-slate-400">Cinema Poster Preview</span>
                </div>
              )}

              {/* Gradient fade to card background */}
              <div className="absolute inset-0 poster-gradient-overlay" />

              {/* Status & Category Pills at top */}
              <div className="absolute top-4 left-4 right-4 flex items-center justify-between">
                <span className="rounded-xl border border-white/20 bg-black/60 px-2.5 py-1 text-[11px] font-black uppercase tracking-wider text-white backdrop-blur-md">
                  {event.event_type}
                </span>

                <span
                  className={`rounded-xl px-2.5 py-1 text-[11px] font-black uppercase tracking-wider backdrop-blur-md ${event.status === "published"
                      ? "border border-emerald-500/40 bg-emerald-950/80 text-emerald-400"
                      : "border border-amber-500/40 bg-amber-950/80 text-amber-300"
                    }`}
                >
                  {event.status}
                </span>
              </div>
            </div>

            {/* Event Information Section */}
            <div className="flex flex-1 flex-col p-6 -mt-8 relative z-10">
              <h3 className="text-2xl font-black text-white tracking-tight line-clamp-1 group-hover:text-blue-400 transition-colors">
                {event.title}
              </h3>

              {/* Badges row matching reference: [7+], [ENG], [4DX Dolby Atmos] */}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="rounded-lg border border-slate-700 bg-slate-900/90 px-2 py-0.5 text-[11px] font-bold text-slate-300">
                  U/A
                </span>
                {event.language && (
                  <span className="rounded-lg border border-slate-700 bg-slate-900/90 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-300">
                    {event.language}
                  </span>
                )}
                {event.genre && (
                  <span className="rounded-lg border border-blue-500/30 bg-blue-950/50 px-2 py-0.5 text-[11px] font-bold text-blue-300">
                    {event.genre}
                  </span>
                )}
                {event.duration_minutes && (
                  <span className="rounded-lg border border-slate-700 bg-slate-900/90 px-2 py-0.5 text-[11px] font-medium text-slate-400">
                    ⏱️ {event.duration_minutes}m
                  </span>
                )}
              </div>

              {event.description && (
                <p className="mt-3 text-xs text-slate-400 line-clamp-2 leading-relaxed">
                  {event.description}
                </p>
              )}

              {/* Perforated ticket tear line with side punch notches */}
              <div className="my-5 ticket-tear relative" />

              {/* Action row matching reference blue button */}
              <div className="mt-auto flex items-center justify-between gap-4">
                <div className="text-[11px] font-mono text-slate-500">
                  REF: {event.id.substring(0, 8)}
                </div>

                <div className="flex items-center gap-2 flex-1">
                  <button
                    onClick={() => onSelectEventForShow(event.id)}
                    className="flex-1 rounded-2xl bg-blue-600 px-4 py-3 text-center text-xs font-bold text-white shadow-glow hover:bg-blue-500 transition-all hover:scale-[1.02] active:scale-[0.98]"
                  >
                    + Schedule Show
                  </button>
                  {onDeleteEvent && (
                    <button
                      type="button"
                      onClick={() => onDeleteEvent(event.id)}
                      className="rounded-2xl border border-rose-500/30 bg-rose-950/30 px-3.5 py-3 text-xs font-bold text-rose-400 hover:bg-rose-900/50 hover:text-rose-200 transition-colors"
                      title="Delete movie"
                    >
                      🗑️
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
