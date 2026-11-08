"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";

export default function BrowsePage() {
  const [shows, setShows] = useState<any[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    city: "",
    event_type: "",
    search: "",
  });

  const load = async () => {
    setLoading(true);

    try {
      const params: Record<string, string> = {};
      if (filters.city) params.city = filters.city;
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.search) params.search = filters.search;

      const data = await browseApi.shows(params);
      setShows(data);
    } catch (error: any) {
      toast.error(error.message || "Failed to load shows");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    browseApi.cities().then(setCities).catch(() => {});
    load();
    // Load the initial show list and city options on page entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateFilter =
    (key: string) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setFilters((current) => ({ ...current, [key]: event.target.value }));
    };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-blue-400">
          Find your next experience
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Movies &amp; Shows
        </h1>
        <p className="mt-2 text-sm text-slate-400 sm:text-base">
          Discover what’s playing near you.
        </p>
      </header>

      <section
        aria-label="Filter shows"
        className="mb-8 grid gap-3 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 sm:grid-cols-2 lg:grid-cols-[1fr_190px_190px_auto]"
      >
        <input
          className="input"
          aria-label="Search shows or venues"
          placeholder="Search movies or venues"
          value={filters.search}
          onChange={updateFilter("search")}
          onKeyDown={(event) => {
            if (event.key === "Enter") load();
          }}
        />

        <select
          className="input"
          aria-label="Filter by city"
          value={filters.city}
          onChange={updateFilter("city")}
        >
          <option value="">All cities</option>
          {cities.map((city) => (
            <option key={city} value={city}>
              {city}
            </option>
          ))}
        </select>

        <select
          className="input"
          aria-label="Filter by show type"
          value={filters.event_type}
          onChange={updateFilter("event_type")}
        >
          <option value="">All types</option>
          {["movie", "concert", "theatre", "other"].map((type) => (
            <option key={type} value={type}>
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </option>
          ))}
        </select>

        <button onClick={load} className="btn-primary">
          Search
        </button>
      </section>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Now showing</h2>
        {!loading && (
          <span className="text-sm text-slate-400">
            {shows.length} {shows.length === 1 ? "show" : "shows"}
          </span>
        )}
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 py-16 text-center text-slate-400">
          Loading shows…
        </div>
      ) : shows.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-16 text-center">
          <p className="mb-3 text-4xl" aria-hidden="true">
            🎬
          </p>
          <p className="font-semibold text-white">No shows found</p>
          <p className="mt-1 text-sm text-slate-400">
            Try a different search or filter.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {shows.map((show) => (
            <Link
              key={show.show_id}
              href={`/shows/${show.show_id}/seats`}
              className="group overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 transition hover:-translate-y-1 hover:border-blue-500/70 hover:shadow-xl hover:shadow-blue-950/30"
            >
              {show.poster_url ? (
                <img
                  src={show.poster_url}
                  alt={`${show.title} poster`}
                  className="h-64 w-full object-cover transition duration-300 group-hover:scale-[1.02]"
                />
              ) : (
                <div className="flex h-64 items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950">
                  <span className="text-6xl" aria-hidden="true">
                    🎥
                  </span>
                </div>
              )}

              <div className="p-5">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <h3 className="text-lg font-bold text-white transition group-hover:text-blue-400">
                    {show.title}
                  </h3>
                  <span className="shrink-0 rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300">
                    {show.event_type || "Show"}
                  </span>
                </div>

                <p className="text-sm text-slate-400">
                  {show.language || "Language not listed"}
                </p>
                <p className="mt-3 text-sm text-slate-300">
                  <span aria-hidden="true">📍 </span>
                  {show.venue_name}
                  {show.city ? `, ${show.city}` : ""}
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  <span aria-hidden="true">◷ </span>
                  {formatTime(show.start_time)}
                </p>

                <div className="mt-5 flex items-center justify-between border-t border-slate-800 pt-4">
                  <span className="text-lg font-bold text-blue-400">
                    ₹{show.base_price}
                  </span>
                  <span className="text-sm text-slate-400">
                    {show.available_seats ?? "—"} seats
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}