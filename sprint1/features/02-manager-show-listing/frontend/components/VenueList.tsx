"use client";

import React, { useState } from "react";
import { createVenueScreen } from "../lib/api";
import { ScreenItem, VenueItem } from "../lib/types";

interface VenueListProps {
  venues: VenueItem[];
  loading: boolean;
  onOpenCreateVenue: () => void;
  onDeleteVenue: (venueId: string) => void;
  onScreenAdded: (venueId: string, newScreen: ScreenItem) => void;
}

export default function VenueList({
  venues,
  loading,
  onOpenCreateVenue,
  onDeleteVenue,
  onScreenAdded,
}: VenueListProps) {
  const [addingScreenForVenueId, setAddingScreenForVenueId] = useState<string | null>(null);
  const [newScreenName, setNewScreenName] = useState("");
  const [newScreenCapacity, setNewScreenCapacity] = useState<number | "">(150);
  const [addingLoading, setAddingLoading] = useState(false);
  const [addingError, setAddingError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="cinema-device-frame h-[420px] animate-pulse bg-slate-900/40" />
        ))}
      </div>
    );
  }

  if (venues.length === 0) {
    return (
      <div className="cinema-device-frame mx-auto max-w-xl p-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-blue-500/20 text-3xl shadow-[0_0_25px_rgba(59,130,246,0.25)]">
          🏛️
        </div>
        <h3 className="mt-5 text-xl font-bold text-white">No Cinema Venues Registered</h3>
        <p className="mt-2 text-sm text-slate-400">
          Add your multiplex, cinema hall, or theater with auditorium screens to schedule shows.
        </p>
        <div className="mt-6">
          <button
            onClick={onOpenCreateVenue}
            className="rounded-2xl bg-blue-600 px-6 py-3 text-xs font-bold text-white shadow-glow hover:bg-blue-500 transition-all"
          >
            + Add First Cinema Venue
          </button>
        </div>
      </div>
    );
  }

  async function handleAddScreenSubmit(venueId: string) {
    setAddingError(null);
    if (!newScreenName.trim()) {
      setAddingError("Screen name is required.");
      return;
    }
    if (!newScreenCapacity || Number(newScreenCapacity) <= 0) {
      setAddingError("Capacity must be greater than 0.");
      return;
    }

    setAddingLoading(true);
    try {
      const created = await createVenueScreen(venueId, {
        name: newScreenName.trim(),
        capacity: Number(newScreenCapacity),
      });
      onScreenAdded(venueId, created);
      setAddingScreenForVenueId(null);
      setNewScreenName("");
      setNewScreenCapacity(150);
    } catch (err: any) {
      setAddingError(err.message || "Failed to add screen.");
    } finally {
      setAddingLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      {venues.map((venue) => {
        const screensCount = venue.screens?.length || 0;
        const totalCapacity =
          venue.screens?.reduce((acc, s) => acc + (s.capacity || 0), 0) || 0;

        const isAddingScreen = addingScreenForVenueId === venue.id;

        return (
          <div key={venue.id} className="cinema-device-frame flex flex-col justify-between group">
            {/* Header Banner */}
            <div className="p-6 border-b border-blue-900/30 bg-[#070b16]">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-700 to-blue-500 text-white font-bold text-xl shadow-glow">
                    🏛️
                  </div>
                  <div>
                    <span className="rounded-lg border border-blue-500/30 bg-blue-950/60 px-2.5 py-0.5 text-[10px] font-bold text-blue-300">
                      {venue.city.toUpperCase()}
                      {venue.state ? `, ${venue.state.toUpperCase()}` : ""}
                    </span>
                    <h3 className="mt-1 text-lg font-black text-white drop-shadow truncate">
                      {venue.name}
                    </h3>
                  </div>
                </div>

                {/* Delete Venue Button */}
                <button
                  type="button"
                  onClick={() => onDeleteVenue(venue.id)}
                  className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-2.5 text-xs font-bold text-rose-400 hover:bg-rose-900/50 hover:text-rose-200 transition-colors"
                  title="Delete Cinema Venue"
                >
                  🗑️
                </button>
              </div>

              {venue.address && (
                <p className="mt-3 text-xs text-slate-400 truncate">
                  📍 {venue.address}
                  {venue.pincode ? ` - ${venue.pincode}` : ""}
                </p>
              )}
            </div>

            {/* Screens & Capacity Summary */}
            <div className="p-6 flex-1 flex flex-col justify-between space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl border border-slate-800 bg-[#050711] p-3">
                  <span className="block text-[10px] font-bold uppercase text-slate-500">
                    Total Auditoriums
                  </span>
                  <span className="font-bold text-white text-base">
                    {screensCount} {screensCount === 1 ? "Screen" : "Screens"}
                  </span>
                </div>

                <div className="rounded-xl border border-slate-800 bg-[#050711] p-3">
                  <span className="block text-[10px] font-bold uppercase text-slate-500">
                    Total Capacity
                  </span>
                  <span className="font-bold text-blue-400 text-base">
                    🪑 {totalCapacity} seats
                  </span>
                </div>
              </div>

              {/* Screens List */}
              <div className="rounded-2xl border border-slate-800 bg-[#050711] p-3.5 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold uppercase tracking-wider text-slate-400 text-[10px]">
                    Auditorium Screens
                  </span>
                  {!isAddingScreen && (
                    <button
                      type="button"
                      onClick={() => {
                        setAddingScreenForVenueId(venue.id);
                        setNewScreenName(`Audi ${screensCount + 1}`);
                        setNewScreenCapacity(150);
                        setAddingError(null);
                      }}
                      className="text-[11px] font-bold text-blue-400 hover:text-blue-300"
                    >
                      + Add Screen
                    </button>
                  )}
                </div>

                {venue.screens && venue.screens.length > 0 ? (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {venue.screens.map((s) => (
                      <div
                        key={s.id}
                        className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-[#0a0f1d] px-3 py-1.5 text-xs"
                      >
                        <span className="font-medium text-slate-200">{s.name}</span>
                        <span className="text-[11px] font-bold text-slate-400">
                          {s.capacity} seats
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-500 italic py-1">
                    No screens configured yet.
                  </p>
                )}

                {/* Inline Add Screen Form */}
                {isAddingScreen && (
                  <div className="mt-3 rounded-xl border border-blue-500/40 bg-blue-950/30 p-3 space-y-2.5 animate-in fade-in">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-blue-300">New Screen</span>
                      <button
                        type="button"
                        onClick={() => setAddingScreenForVenueId(null)}
                        className="text-xs text-slate-400 hover:text-white"
                      >
                        ✕
                      </button>
                    </div>

                    {addingError && (
                      <div className="text-[10px] text-rose-300 bg-rose-950/50 p-1.5 rounded">
                        {addingError}
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="Name (e.g. Audi 2)"
                        value={newScreenName}
                        onChange={(e) => setNewScreenName(e.target.value)}
                        className="flex-1 rounded-lg border border-slate-700 bg-[#070b16] px-2.5 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                      />
                      <input
                        type="number"
                        min={1}
                        placeholder="Seats"
                        value={newScreenCapacity}
                        onChange={(e) =>
                          setNewScreenCapacity(
                            e.target.value === "" ? "" : Number(e.target.value)
                          )
                        }
                        className="w-20 rounded-lg border border-slate-700 bg-[#070b16] px-2.5 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                      />
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setAddingScreenForVenueId(null)}
                        className="px-2.5 py-1 text-[11px] font-medium text-slate-400 hover:text-white"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={addingLoading}
                        onClick={() => handleAddScreenSubmit(venue.id)}
                        className="rounded-lg bg-blue-600 px-3 py-1 text-[11px] font-bold text-white shadow-glow hover:bg-blue-500 disabled:opacity-50"
                      >
                        {addingLoading ? "Adding..." : "Save Screen"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
