"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createShow, fetchScreenSeatCount } from "../lib/api";
import {
  CreateShowPayload,
  EventItem,
  SeatCountInfo,
  ShowItem,
  VenueItem,
} from "../lib/types";

interface CreateShowModalProps {
  isOpen: boolean;
  onClose: () => void;
  events: EventItem[];
  venues: VenueItem[];
  initialEventId?: string;
  onShowCreated: (newShow: ShowItem) => void;
}

export default function CreateShowModal({
  isOpen,
  onClose,
  events,
  venues,
  initialEventId,
  onShowCreated,
}: CreateShowModalProps) {
  const router = useRouter();

  const [selectedEventId, setSelectedEventId] = useState<string>(initialEventId || "");
  const [selectedVenueId, setSelectedVenueId] = useState<string>("");
  const [selectedScreenId, setSelectedScreenId] = useState<string>("");

  const [date, setDate] = useState<string>("");
  const [startTime, setStartTime] = useState<string>("18:35");
  const [endTime, setEndTime] = useState<string>("20:45");

  const [seatInfo, setSeatInfo] = useState<SeatCountInfo | null>(null);
  const [loadingSeats, setLoadingSeats] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync initial event if provided
  useEffect(() => {
    if (initialEventId) {
      setSelectedEventId(initialEventId);
    } else if (events.length > 0 && !selectedEventId) {
      setSelectedEventId(events[0].id);
    }
  }, [initialEventId, events]);

  // Set default venue and screen
  useEffect(() => {
    if (venues.length > 0 && !selectedVenueId) {
      setSelectedVenueId(venues[0].id);
      if (venues[0].screens && venues[0].screens.length > 0) {
        setSelectedScreenId(venues[0].screens[0].id);
      }
    }
  }, [venues]);

  const currentVenue = venues.find((v) => v.id === selectedVenueId);
  const currentScreens = currentVenue?.screens || [];

  useEffect(() => {
    if (currentScreens.length > 0 && !currentScreens.find((s) => s.id === selectedScreenId)) {
      setSelectedScreenId(currentScreens[0].id);
    }
  }, [currentVenue]);

  // Query authoritative seat count for selected screen
  useEffect(() => {
    if (selectedScreenId) {
      setLoadingSeats(true);
      fetchScreenSeatCount(selectedScreenId)
        .then((info) => setSeatInfo(info))
        .catch(() => setSeatInfo(null))
        .finally(() => setLoadingSeats(false));
    } else {
      setSeatInfo(null);
    }
  }, [selectedScreenId]);

  // Auto-calculate end time
  useEffect(() => {
    const ev = events.find((e) => e.id === selectedEventId);
    const duration = ev?.duration_minutes || 120;
    if (startTime) {
      const [hours, minutes] = startTime.split(":").map(Number);
      const totalStartMinutes = hours * 60 + minutes;
      const totalEndMinutes = totalStartMinutes + duration + 15;
      const endH = Math.floor(totalEndMinutes / 60) % 24;
      const endM = totalEndMinutes % 60;
      setEndTime(
        `${String(endH).padStart(2, "0")}:${String(endM).padStart(2, "0")}`
      );
    }
  }, [startTime, selectedEventId, events]);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!selectedEventId) {
      setError("Please select an event.");
      return;
    }
    if (!selectedScreenId) {
      setError("Please select a screen.");
      return;
    }
    if (!date) {
      setError("Please select a date for the show.");
      return;
    }

    const startIso = new Date(`${date}T${startTime}:00`).toISOString();
    const endIso = new Date(`${date}T${endTime}:00`).toISOString();

    if (new Date(endIso) <= new Date(startIso)) {
      setError("Show end time must be after start time.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: CreateShowPayload = {
        event_id: selectedEventId,
        screen_id: selectedScreenId,
        start_time: startIso,
        end_time: endIso,
      };

      const created = await createShow(payload);
      onShowCreated(created);
      onClose();

      const seatCount = seatInfo?.seat_count || created.seat_count || 0;
      router.push(
        `/pricing?show_id=${created.id}&event_id=${created.event_id}&screen_id=${created.screen_id}&seat_count=${seatCount}`
      );
    } catch (err: any) {
      setError(err.message || "Failed to schedule show. Please check for scheduling conflicts.");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedEvent = events.find((e) => e.id === selectedEventId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md animate-fadeIn">
      <div className="cinema-device-frame relative w-full max-w-lg max-h-[92vh] overflow-y-auto p-6 sm:p-8 bg-[#090d1a] border-2 border-blue-600 shadow-glow">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">🎟️</span>
              <h3 className="text-xl font-black text-white tracking-tight">Schedule Cinema Show</h3>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Select venue, screen, and schedule before passing to seat pricing.
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-950/60 p-3 text-xs font-medium text-rose-300">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          {/* Select Event */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
              Movie / Event <span className="text-blue-400">*</span>
            </label>
            <select
              value={selectedEventId}
              onChange={(e) => setSelectedEventId(e.target.value)}
              className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-4 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
            >
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.title} ({ev.event_type}) — {ev.duration_minutes ? `${ev.duration_minutes}m` : "No duration"}
                </option>
              ))}
            </select>
          </div>

          {/* Venue & Screen */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                  Cinema Venue <span className="text-blue-400">*</span>
                </label>
                <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider">
                  Type: Cinema (Fixed)
                </span>
              </div>
              <select
                value={selectedVenueId}
                onChange={(e) => setSelectedVenueId(e.target.value)}
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3.5 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              >
                {venues.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.city})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Auditorium Screen <span className="text-blue-400">*</span>
              </label>
              <select
                value={selectedScreenId}
                onChange={(e) => setSelectedScreenId(e.target.value)}
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3.5 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              >
                {currentScreens.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} (Cap: {s.capacity})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Seat Capacity breakdown card */}
          <div className="rounded-2xl border border-blue-500/30 bg-[#0d1326] p-4">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-300">Authoritative Physical Capacity:</span>
              {loadingSeats ? (
                <span className="text-slate-400">Loading seat count...</span>
              ) : seatInfo ? (
                <span className="rounded-lg border border-blue-400/40 bg-blue-900/60 px-2.5 py-1 font-mono font-bold text-blue-200">
                  {seatInfo.seat_count} seats (via {seatInfo.source})
                </span>
              ) : (
                <span className="text-slate-400">—</span>
              )}
            </div>
          </div>

          {/* Date & Time selection */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Date <span className="text-blue-400">*</span>
              </label>
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3 py-2.5 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Start Time <span className="text-blue-400">*</span>
              </label>
              <input
                type="time"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3 py-2.5 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                End Time <span className="text-blue-400">*</span>
              </label>
              <input
                type="time"
                required
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3 py-2.5 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Ticket tear line */}
          <div className="ticket-tear my-4" />

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-2xl px-5 py-3 text-xs font-bold text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 rounded-2xl bg-blue-600 py-3.5 text-xs font-bold text-white shadow-glow hover:bg-blue-500 disabled:opacity-50 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {submitting ? "Checking Conflicts & Saving..." : "Continue to Seat Selection →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
