"use client";

import React, { useState } from "react";
import { createVenue } from "../lib/api";
import { CreateScreenInput, CreateVenuePayload, VenueItem } from "../lib/types";

interface CreateVenueModalProps {
  isOpen: boolean;
  onClose: () => void;
  onVenueCreated: (newVenue: VenueItem) => void;
}

export default function CreateVenueModal({
  isOpen,
  onClose,
  onVenueCreated,
}: CreateVenueModalProps) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [stateName, setStateName] = useState("");
  const [pincode, setPincode] = useState("");

  // Screens list
  const [screens, setScreens] = useState<CreateScreenInput[]>([
    { name: "Audi 1 (Standard)", capacity: 150 },
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  function handleAddScreen() {
    setScreens((prev) => [
      ...prev,
      { name: `Audi ${prev.length + 1} (Standard)`, capacity: 120 },
    ]);
  }

  function handleRemoveScreen(index: number) {
    if (screens.length <= 1) return;
    setScreens((prev) => prev.filter((_, i) => i !== index));
  }

  function handleScreenChange(
    index: number,
    field: keyof CreateScreenInput,
    value: string | number
  ) {
    setScreens((prev) =>
      prev.map((s, i) => {
        if (i !== index) return s;
        if (field === "capacity") {
          return { ...s, capacity: Number(value) || 0 };
        }
        return { ...s, name: String(value) };
      })
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Cinema venue name is required.");
      return;
    }
    if (!city.trim()) {
      setError("City is required.");
      return;
    }

    // Validate screens
    for (let i = 0; i < screens.length; i++) {
      const s = screens[i];
      if (!s.name.trim()) {
        setError(`Screen #${i + 1} must have a name.`);
        return;
      }
      if (!s.capacity || s.capacity <= 0) {
        setError(`Screen #${i + 1} capacity must be greater than 0.`);
        return;
      }
    }

    setLoading(true);
    try {
      const payload: CreateVenuePayload = {
        name: name.trim(),
        city: city.trim(),
        address: address.trim() || undefined,
        state: stateName.trim() || undefined,
        pincode: pincode.trim() || undefined,
        screens: screens.map((s) => ({
          name: s.name.trim(),
          capacity: Number(s.capacity),
        })),
      };

      const created = await createVenue(payload);
      onVenueCreated(created);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create cinema venue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl rounded-3xl border border-blue-500/30 bg-[#0a0f1d] p-6 sm:p-8 shadow-[0_0_50px_rgba(37,99,235,0.25)] text-slate-100 max-h-[92vh] overflow-y-auto">
        {/* Glow Accent */}
        <div className="absolute -top-24 -left-24 h-48 w-48 rounded-full bg-blue-600/20 blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between pb-6 border-b border-blue-900/30">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-700 to-blue-500 text-white font-bold text-xl shadow-glow">
              🏛️
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-wide">
                Add Cinema Venue
              </h2>
              <p className="text-xs text-slate-400">
                Register a new multiplex, theatre, or auditorium with screens
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-800 bg-[#0d1326] text-slate-400 hover:text-white hover:border-slate-700 transition-colors"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-950/40 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          {/* Cinema Name */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
              Cinema / Venue Name *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. PVR ICON: Nexus Mall"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-[#050711] px-4 py-2.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
            />
          </div>

          {/* City & State */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                City *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Mumbai, Bengaluru"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-[#050711] px-4 py-2.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                State
              </label>
              <input
                type="text"
                placeholder="e.g. Maharashtra"
                value={stateName}
                onChange={(e) => setStateName(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-[#050711] px-4 py-2.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
              />
            </div>
          </div>

          {/* Address & PIN */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                Street Address / Mall
              </label>
              <input
                type="text"
                placeholder="e.g. 4th Floor, Nexus Grand"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-[#050711] px-4 py-2.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                PIN Code
              </label>
              <input
                type="text"
                placeholder="e.g. 400053"
                value={pincode}
                onChange={(e) => setPincode(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-[#050711] px-4 py-2.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
              />
            </div>
          </div>

          {/* Screens Section */}
          <div className="rounded-2xl border border-blue-900/30 bg-[#070b16] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm">💺</span>
                <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                  Auditorium Screens ({screens.length})
                </span>
              </div>
              <button
                type="button"
                onClick={handleAddScreen}
                className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-2.5 py-1 text-[11px] font-bold text-blue-400 hover:bg-blue-500/20 transition-colors"
              >
                + Add Screen
              </button>
            </div>

            <p className="text-[11px] text-slate-400">
              Each screen defines the baseline seating capacity for shows scheduled in this cinema.
            </p>

            <div className="space-y-2.5 pt-1">
              {screens.map((screen, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-3 rounded-xl border border-slate-800/80 bg-[#050711] p-2.5"
                >
                  <div className="flex-1">
                    <input
                      type="text"
                      required
                      placeholder="Screen Name (e.g. Audi 1)"
                      value={screen.name}
                      onChange={(e) =>
                        handleScreenChange(idx, "name", e.target.value)
                      }
                      className="w-full rounded-lg border border-slate-800 bg-[#0d1326] px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div className="w-28">
                    <input
                      type="number"
                      required
                      min={1}
                      placeholder="Capacity"
                      value={screen.capacity}
                      onChange={(e) =>
                        handleScreenChange(idx, "capacity", e.target.value)
                      }
                      className="w-full rounded-lg border border-slate-800 bg-[#0d1326] px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  {screens.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveScreen(idx)}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      title="Remove Screen"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-blue-900/30">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-xl border border-slate-800 bg-transparent px-4 py-2.5 text-xs font-bold text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-blue-600 px-6 py-2.5 text-xs font-bold text-white shadow-glow hover:bg-blue-500 disabled:opacity-50 transition-all"
            >
              {loading ? "Creating Venue..." : "Create Cinema Venue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
