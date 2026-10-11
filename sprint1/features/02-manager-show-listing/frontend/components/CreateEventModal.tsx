"use client";

import React, { useState } from "react";
import { createEvent } from "../lib/api";
import { CreateEventPayload, EventItem, EventStatus, EventType } from "../lib/types";

interface CreateEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  onEventCreated: (newEvent: EventItem) => void;
}

export default function CreateEventModal({
  isOpen,
  onClose,
  onEventCreated,
}: CreateEventModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] = useState<EventType>("movie");
  const [durationMinutes, setDurationMinutes] = useState<number | "">(120);
  const [language, setLanguage] = useState("English");
  const [genre, setGenre] = useState("Action");
  const [posterUrl, setPosterUrl] = useState("");
  const [status, setStatus] = useState<EventStatus>("published");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("Event title is required.");
      return;
    }

    setLoading(true);
    try {
      const payload: CreateEventPayload = {
        title: title.trim(),
        description: description.trim() || undefined,
        event_type: eventType,
        duration_minutes: durationMinutes === "" ? undefined : Number(durationMinutes),
        language: language.trim() || undefined,
        genre: genre.trim() || undefined,
        poster_url: posterUrl.trim() || undefined,
        status,
      };

      const created = await createEvent(payload);
      onEventCreated(created);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create event. Please verify backend connection.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md animate-fadeIn">
      <div className="cinema-device-frame relative w-full max-w-lg max-h-[92vh] overflow-y-auto p-6 sm:p-8 bg-[#090d1a] border-2 border-blue-600 shadow-glow">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">🎬</span>
              <h3 className="text-xl font-black text-white tracking-tight">Create New Event</h3>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Add a movie or live performance to the cinema catalogue.
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
          {/* Title */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
              Event Title <span className="text-blue-400">*</span>
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Sonic The Hedgehog 2, Spider-Man"
              className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-4 py-3 text-sm font-semibold text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Event Type & Genre */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Venue / Event Type
              </label>
              <div className="mt-1.5 flex items-center justify-between rounded-2xl border border-blue-500/40 bg-[#0d1326] px-4 py-3 text-sm font-bold text-blue-300">
                <span className="flex items-center gap-2">
                  <span>🎬</span>
                  <span>Cinema (Movie)</span>
                </span>
                <span className="rounded-lg bg-blue-900/60 px-2 py-0.5 text-[10px] uppercase font-bold text-blue-200">
                  Fixed
                </span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Genre
              </label>
              <input
                type="text"
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                placeholder="e.g. Adventure, Sci-Fi"
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3.5 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Duration & Language */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Duration (min)
              </label>
              <input
                type="number"
                min="1"
                value={durationMinutes}
                onChange={(e) =>
                  setDurationMinutes(e.target.value === "" ? "" : Number(e.target.value))
                }
                placeholder="122"
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3.5 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                Language
              </label>
              <input
                type="text"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                placeholder="English"
                className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-3.5 py-3 text-sm font-semibold text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Poster Image URL */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
              Poster Image URL
            </label>
            <input
              type="url"
              value={posterUrl}
              onChange={(e) => setPosterUrl(e.target.value)}
              placeholder="https://res.cloudinary.com/... or image link"
              className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
            {posterUrl && (
              <div className="mt-3 flex items-center gap-3 rounded-2xl border border-slate-800 bg-[#0d1326] p-2.5">
                <img
                  src={posterUrl}
                  alt="Poster Preview"
                  className="h-16 w-12 rounded-xl object-cover shadow-sm"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      "https://images.unsplash.com/photo-1536440136628-849c177e76a1?q=80&w=600&auto=format&fit=crop";
                  }}
                />
                <span className="text-xs font-medium text-slate-300">Live Poster Preview</span>
              </div>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
              Synopsis
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Plot overview, director, cast..."
              className="mt-1.5 w-full rounded-2xl border border-slate-700 bg-[#0d1326] px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Ticket tear line */}
          <div className="ticket-tear my-4" />

          {/* Actions */}
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
              disabled={loading}
              className="flex-1 rounded-2xl bg-blue-600 py-3.5 text-xs font-bold text-white shadow-glow hover:bg-blue-500 disabled:opacity-50 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {loading ? "Persisting to Supabase..." : "Save Event to Catalogue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
