"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";

const EVENT_TYPES = [
  { label: "All", value: "" },
  { label: "🎬 Movies", value: "movie" },
  { label: "🎵 Concerts", value: "concert" },
  { label: "🎭 Theatre", value: "theatre" },
  { label: "✨ Other", value: "other" },
];

const LANGUAGES = ["Hindi", "English", "Gujarati", "Tamil", "Telugu", "Marathi"];
const RECENT_STORAGE_KEY = "ticketflow_recent_searches";

function getDateOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

export default function BrowsePage() {
  const [shows, setShows] = useState<any[]>([]);
  const [allShowsCache, setAllShowsCache] = useState<any[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [trending, setTrending] = useState<string[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchInput, setSearchInput] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const searchBoxRef = useRef<HTMLDivElement>(null);

  const [filters, setFilters] = useState({
    city: "",
    event_type: "",
    language: "",
    date: "",
    sort_by: "time_asc",
    search: "",
  });

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(RECENT_STORAGE_KEY) || "[]");
      if (Array.isArray(saved)) setRecentSearches(saved.slice(0, 5));
    } catch {}
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const saveRecentSearch = useCallback((term: string) => {
    const clean = term.trim();
    if (clean.length < 2) return;
    setRecentSearches((prev) => {
      const updated = [
        clean,
        ...prev.filter((item) => item.toLowerCase() !== clean.toLowerCase()),
      ].slice(0, 5);
      try {
        localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filters.city) params.city = filters.city;
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.language) params.language = filters.language;
      if (filters.date) params.date = filters.date;
      if (filters.sort_by) params.sort_by = filters.sort_by;
      if (filters.search.trim()) params.search = filters.search.trim();

      const data = await browseApi.shows(params);
      setShows(data);

      if (!filters.search.trim() && data.length > 0) {
        setAllShowsCache(data);
        const uniqueTitles = Array.from(
          new Set(data.map((s: any) => s.title).filter(Boolean))
        ).slice(0, 5) as string[];
        setTrending(uniqueTitles);
      }
    } catch (error: any) {
      toast.error(error.message || "Failed to load shows");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    browseApi.cities().then(setCities).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updateFilter = (key: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  // Triggered explicitly on Search button click or Enter key
  const executeSearch = () => {
    const trimmed = searchInput.trim();
    if (trimmed) saveRecentSearch(trimmed);
    setFilters((prev) => ({ ...prev, search: searchInput }));
    setDropdownOpen(false);
  };

  const selectSuggestion = (term: string) => {
    setSearchInput(term);
    setFilters((prev) => ({ ...prev, search: term }));
    saveRecentSearch(term);
    setDropdownOpen(false);
  };

  const clearSearchOnly = () => {
    setSearchInput("");
    setFilters((prev) => ({ ...prev, search: "" }));
    setDropdownOpen(true);
  };

  const resetAllFilters = () => {
    setSearchInput("");
    setFilters({
      city: "",
      event_type: "",
      language: "",
      date: "",
      sort_by: "time_asc",
      search: "",
    });
  };

  // Instant client-side suggestions inside dropdown while typing (no API flicker)
  const localSuggestions = searchInput.trim()
    ? allShowsCache
        .filter((s) => {
          const q = searchInput.toLowerCase().trim();
          return (
            s.title?.toLowerCase().includes(q) ||
            s.venue_name?.toLowerCase().includes(q) ||
            s.city?.toLowerCase().includes(q) ||
            s.genre?.toLowerCase().includes(q)
          );
        })
        .slice(0, 5)
    : [];

  const activeFilterCount = [
    filters.city,
    filters.event_type,
    filters.language,
    filters.date,
    filters.search.trim(),
  ].filter(Boolean).length;

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

  const todayStr = getDateOffset(0);
  const tomorrowStr = getDateOffset(1);

  // Shared grid classes: 1 col on phones, up to 5 on very wide monitors
  const gridClasses =
    "grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5";

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1800px] px-4 py-8 sm:px-6 lg:px-10 2xl:px-16">
      {/* Header */}
      <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-blue-400">
            Find your next experience
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Movies &amp; Shows
          </h1>
          <p className="mt-1 text-sm text-slate-400 sm:text-base">
            Search by movie, venue, genre, language, or city.
          </p>
        </div>

        {/* City Selector in Header */}
        <div className="w-full sm:w-52">
          <select
            className="input w-full"
            aria-label="Filter by city"
            value={filters.city}
            onChange={(e) => updateFilter("city", e.target.value)}
          >
            <option value="">📍 All Cities</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                📍 {city}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Main Search & Filter Panel */}
      <section
        aria-label="Search and filter shows"
        className="mb-8 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 sm:p-5"
      >
        {/* Row 1: Search Input + Search Button + Language + Sort */}
        <div className="grid gap-3 md:grid-cols-[1fr_auto_180px_230px]">
          <div ref={searchBoxRef} className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-slate-400"
            >
              🔍
            </span>
            <input
              style={{ paddingLeft: "2.6rem", paddingRight: "2.4rem" }}
              className="input w-full"
              aria-label="Search movies, venues, genres, or cities"
              placeholder="Search for Movies, Events, Plays, Venues, or Genres..."
              value={searchInput}
              onFocus={() => setDropdownOpen(true)}
              onChange={(e) => {
                setSearchInput(e.target.value);
                setDropdownOpen(true);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") executeSearch();
                if (e.key === "Escape") setDropdownOpen(false);
              }}
            />
            {searchInput && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={clearSearchOnly}
                className="absolute inset-y-0 right-3 flex items-center text-sm text-slate-400 hover:text-white"
              >
                ✕
              </button>
            )}

            {/* Dropdown inside Mid Search Bar */}
            {dropdownOpen && (
              <div className="absolute left-0 right-0 top-full z-40 mt-2 overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
                {searchInput.trim() ? (
                  <div className="p-2">
                    <p className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      Quick Suggestions (Press Search for fuzzy match)
                    </p>
                    {localSuggestions.length > 0 ? (
                      <div className="mt-1 space-y-1">
                        {localSuggestions.map((show) => (
                          <div
                            key={`drop-${show.show_id}`}
                            className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 transition hover:bg-slate-800"
                          >
                            <button
                              type="button"
                              onClick={() => selectSuggestion(show.title)}
                              className="flex min-w-0 flex-1 items-center gap-3 text-left"
                            >
                              {show.poster_url ? (
                                <img
                                  src={show.poster_url}
                                  alt={show.title}
                                  className="h-10 w-8 shrink-0 rounded object-cover"
                                />
                              ) : (
                                <div className="flex h-10 w-8 shrink-0 items-center justify-center rounded bg-slate-800 text-sm">
                                  🎬
                                </div>
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-semibold text-white">
                                  {show.title}
                                </p>
                                <p className="truncate text-xs text-slate-400">
                                  {show.venue_name} • {show.city} • ₹{show.base_price ?? "—"}
                                </p>
                              </div>
                            </button>

                            <Link
                              href={`/shows/${show.show_id}/seats`}
                              onClick={() => {
                                saveRecentSearch(show.title);
                                setDropdownOpen(false);
                              }}
                              className="shrink-0 rounded-lg bg-blue-600/20 px-2.5 py-1 text-xs font-medium text-blue-400 hover:bg-blue-600 hover:text-white"
                            >
                              Book
                            </Link>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex items-center justify-between px-3 py-3">
                        <p className="text-xs text-slate-400">
                          Click Search to find spelling matches for &ldquo;{searchInput.trim()}&rdquo;
                        </p>
                        <button
                          type="button"
                          onClick={executeSearch}
                          className="text-xs font-medium text-blue-400 hover:underline"
                        >
                          Search →
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3 p-3.5">
                    {recentSearches.length > 0 && (
                      <div>
                        <div className="mb-1.5 flex items-center justify-between">
                          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                            🕒 Recent Searches
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              setRecentSearches([]);
                              localStorage.removeItem(RECENT_STORAGE_KEY);
                            }}
                            className="text-[11px] text-slate-500 hover:text-red-400"
                          >
                            Clear
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {recentSearches.map((item) => (
                            <button
                              key={`recent-${item}`}
                              type="button"
                              onClick={() => selectSuggestion(item)}
                              className="rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs text-slate-200 transition hover:border-blue-500 hover:text-white"
                            >
                              {item}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {trending.length > 0 && (
                      <div>
                        <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                          🔥 Trending Now
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {trending.map((title) => (
                            <button
                              key={`trend-${title}`}
                              type="button"
                              onClick={() => selectSuggestion(title)}
                              className="rounded-full border border-blue-500/30 bg-blue-950/40 px-3 py-1 text-xs text-blue-300 transition hover:border-blue-400 hover:text-white"
                            >
                              {title}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {recentSearches.length === 0 && trending.length === 0 && (
                      <p className="py-1 text-xs text-slate-400">
                        Start typing to search movies, venues, genres, or cities...
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Search Button */}
          <button
            type="button"
            onClick={executeSearch}
            className="btn-primary px-5"
          >
            Search
          </button>

          <select
            className="input"
            aria-label="Filter by language"
            value={filters.language}
            onChange={(e) => updateFilter("language", e.target.value)}
          >
            <option value="">All Languages</option>
            {LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {lang}
              </option>
            ))}
          </select>

          <select
            className="input"
            aria-label="Sort shows"
            value={filters.sort_by}
            onChange={(e) => updateFilter("sort_by", e.target.value)}
          >
            <option value="time_asc">Sort: Soonest First</option>
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
            <option value="seats_desc">Most Seats Available</option>
          </select>
        </div>

        {/* Row 2: Event Type Pills + Quick Date Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            {EVENT_TYPES.map((type) => {
              const active = filters.event_type === type.value;
              return (
                <button
                  key={type.label}
                  type="button"
                  onClick={() => updateFilter("event_type", type.value)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
                    active
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-600/40"
                      : "border border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-600 hover:text-white"
                  }`}
                >
                  {type.label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => updateFilter("date", "")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                filters.date === ""
                  ? "bg-slate-700 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              Any Date
            </button>
            <button
              type="button"
              onClick={() => updateFilter("date", todayStr)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                filters.date === todayStr
                  ? "bg-blue-600 text-white"
                  : "border border-slate-700 text-slate-300 hover:border-slate-600"
              }`}
            >
              Today
            </button>
            <button
              type="button"
              onClick={() => updateFilter("date", tomorrowStr)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                filters.date === tomorrowStr
                  ? "bg-blue-600 text-white"
                  : "border border-slate-700 text-slate-300 hover:border-slate-600"
              }`}
            >
              Tomorrow
            </button>
            <input
              type="date"
              aria-label="Pick a specific date"
              value={filters.date}
              onChange={(e) => updateFilter("date", e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>
      </section>

      {/* Results Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-white">
            {filters.search.trim()
              ? `Results for "${filters.search.trim()}"`
              : "Now showing"}
          </h2>
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={resetAllFilters}
              className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 transition hover:border-red-500/60 hover:text-red-400"
            >
              Reset filters ({activeFilterCount})
            </button>
          )}
        </div>

        {!loading && (
          <span className="text-sm text-slate-400">
            {shows.length} {shows.length === 1 ? "show" : "shows"}
          </span>
        )}
      </div>

      {/* Show Cards Grid */}
      {loading ? (
        <div className={gridClasses}>
          {[1, 2, 3, 4, 5].map((n) => (
            <div
              key={n}
              className="h-96 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60"
            />
          ))}
        </div>
      ) : shows.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-16 text-center">
          <p className="mb-3 text-4xl" aria-hidden="true">
            🎬
          </p>
          <p className="font-semibold text-white">No shows matched your search</p>
          <p className="mt-1 text-sm text-slate-400">
            Try clearing some filters or searching for another title, city, or venue.
          </p>
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={resetAllFilters}
              className="btn-primary mt-4"
            >
              Reset All Filters
            </button>
          )}
        </div>
      ) : (
        <div className={gridClasses}>
          {shows.map((show) => (
            <div key={show.show_id} className="flex flex-col">
              <Link
                href={`/shows/${show.show_id}/seats`}
                className="group flex-1 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 transition hover:-translate-y-1 hover:border-blue-500/70 hover:shadow-xl hover:shadow-blue-950/30"
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
                    <span className="shrink-0 rounded-md border border-slate-700 px-2 py-1 text-xs capitalize text-slate-300">
                      {show.event_type || "Show"}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <span>{show.language || "Language N/A"}</span>
                    {show.genre && (
                      <>
                        <span>•</span>
                        <span className="text-slate-300">{show.genre}</span>
                      </>
                    )}
                    {show.duration_minutes && (
                      <>
                        <span>•</span>
                        <span>{show.duration_minutes} mins</span>
                      </>
                    )}
                  </div>

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
                      ₹{show.base_price ?? "—"}
                    </span>
                    <span
                      className={`text-sm font-medium ${
                        (show.available_seats ?? 0) > 0
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {show.available_seats ?? "—"} seats
                    </span>
                  </div>
                </div>
              </Link>

              <Link
                href={`/events/${show.event_id}/reviews`}
                className="mt-2 block rounded-xl border border-slate-800 bg-slate-900/60 py-2 text-center text-sm text-blue-400 transition hover:border-blue-500/70"
              >
                ★ Reviews &amp; Ratings
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
