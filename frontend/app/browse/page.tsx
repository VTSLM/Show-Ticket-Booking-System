"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";
import { useWishlist } from "@/components/useWishlist";
<<<<<<< HEAD
=======
import EventPoster from "@/components/EventPoster";
>>>>>>> origin/main
import ShowCarousel from "@/components/ShowCarousel";
import { useLocation } from "@/contexts/LocationContext";
import { NEARBY_RADIUS_KM, formatDistance } from "@/lib/geo";

const EVENT_TYPES = [
  { label: "All", value: "" },
  { label: "🎬 Movies", value: "movie" },
  { label: "🎵 Concerts", value: "concert" },
  { label: "🎭 Theatre", value: "theatre" },
  { label: "✨ Other", value: "other" },
];

// Rows on the page (one swipeable row per kind of show)
const SECTIONS = [
  { type: "movie", title: "🎬 Movies near you" },
  { type: "concert", title: "🎵 Concerts (all, any distance)" },
  { type: "theatre", title: "🎭 Theatre near you" },
  { type: "other", title: "✨ More near you" },
];

const LANGUAGES = ["Hindi", "English", "Gujarati", "Tamil", "Telugu", "Marathi"];
const RECENT_STORAGE_KEY = "ticketflow_recent_searches";

function getDateOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

const hasRating = (s: any) => Number(s.review_count ?? 0) > 0 && s.avg_rating != null;

// The price the card shows: the current (dynamic) price, else the base price.
const shownPrice = (s: any): number | null => {
  const v = s.current_price ?? s.base_price;
  return v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v);
};

// Sorts the shows on the page itself so the chosen sort always applies,
// whatever order the API returned them in.
function sortShows(list: any[], sortBy: string): any[] {
  const price = shownPrice; // sort by the price customers see on the card
  const time = (s: any) => new Date(s.start_time).getTime() || 0;
  const seats = (s: any) => Number(s.available_seats ?? 0);
  const dist = (s: any) => (s.distance_km == null ? Infinity : Number(s.distance_km));

  return [...list].sort((a, b) => {
    if (sortBy === "distance_asc") {
      return dist(a) - dist(b) || time(a) - time(b); // nearest first
    }
    if (sortBy === "rating_desc") {
      // best rating first, more reviews break ties, unrated shows go last
      const ra = hasRating(a) ? Number(a.avg_rating) : -1;
      const rb = hasRating(b) ? Number(b.avg_rating) : -1;
      if (ra !== rb) return rb - ra;
      return Number(b.review_count ?? 0) - Number(a.review_count ?? 0) || time(a) - time(b);
    }
    if (sortBy === "price_asc" || sortBy === "price_desc") {
      const pa = price(a);
      const pb = price(b);
      if (pa === null && pb !== null) return 1; // shows without a price go last
      if (pa !== null && pb === null) return -1;
      if (pa !== null && pb !== null && pa !== pb) {
        return sortBy === "price_asc" ? pa - pb : pb - pa;
      }
      return time(a) - time(b);
    }
    if (sortBy === "seats_desc") {
      return seats(b) - seats(a) || time(a) - time(b);
    }
    return time(a) - time(b); // time_asc
  });
}

export default function BrowsePage() {
  const wishlist = useWishlist();
  const { location, ready: locationReady, openPicker } = useLocation();
  const [shows, setShows] = useState<any[]>([]);
  const [allShowsCache, setAllShowsCache] = useState<any[]>([]);
  const [trending, setTrending] = useState<string[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchInput, setSearchInput] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const searchBoxRef = useRef<HTMLDivElement>(null);

  const [filters, setFilters] = useState({
    event_type: "",
    language: "",
    date: "",
    sort_by: "distance_asc",
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
    // Without a location only concerts are listed (they have no distance limit)
    if (!location && filters.event_type && filters.event_type !== "concert") {
      setShows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const params: Record<string, string> = location
        ? {
            lat: String(location.lat),
            lng: String(location.lng),
            radius_km: String(NEARBY_RADIUS_KM),
          }
        : { event_type: "concert" };
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.language) params.language = filters.language;
      if (filters.date) params.date = filters.date;
      // "Top rated" is sorted on the page (the rating comes with each show)
      if (filters.sort_by && filters.sort_by !== "rating_desc") params.sort_by = filters.sort_by;
      if (filters.search.trim()) params.search = filters.search.trim();

      const data = await browseApi.shows(params);

      // Group listings by movie/event identity so ANY movie appears EXACTLY ONCE on the page
      const groupedMap = new Map<string, any>();
      (Array.isArray(data) ? data : []).forEach((item: any) => {
        const titleKey = (item.title || "").trim().toLowerCase();
        const key = item.event_id || titleKey || item.show_id;
        if (!groupedMap.has(key)) {
          groupedMap.set(key, {
            ...item,
            all_shows: [item],
            theatres_list: item.venue_name ? [item.venue_name] : [],
            cities_list: item.city ? [item.city] : [],
            theatres_count: item.theatres_count || (item.venue_name ? 1 : 0),
            shows_count: item.shows_count || 1,
          });
        } else {
          const existing = groupedMap.get(key);
          existing.all_shows.push(item);
          if (item.venue_name && !existing.theatres_list.includes(item.venue_name)) {
            existing.theatres_list.push(item.venue_name);
          }
          if (item.city && !existing.cities_list.includes(item.city)) {
            existing.cities_list.push(item.city);
          }
          // Show the cheapest showtime's price, with that showtime's own pricing details
          const itemPrice = shownPrice(item);
          const shown = shownPrice(existing);
          if (itemPrice !== null && (shown === null || itemPrice < shown)) {
            existing.current_price = item.current_price;
            existing.base_price = item.base_price;
            existing.price_change_pct = item.price_change_pct;
            existing.pricing_reasons = item.pricing_reasons;
          }
          existing.available_seats = (existing.available_seats || 0) + (item.available_seats || 0);
          existing.theatres_count = existing.theatres_list.length;
          existing.shows_count = existing.all_shows.length;
        }
      });
      const uniqueShows = Array.from(groupedMap.values());
      const hasSearch = !!filters.search.trim();
      setShows(hasSearch && filters.sort_by === "time_asc" ? uniqueShows : sortShows(uniqueShows, filters.sort_by));

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
  }, [filters, location]);

  useEffect(() => {
    if (!locationReady) return; // wait until the saved location has been read
    load();
  }, [load, locationReady]);

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
      event_type: "",
      language: "",
      date: "",
      sort_by: "distance_asc",
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

  // One show card (fixed width so cards sit side by side in a swipeable row)
  const renderCard = (show: any) => {
    const away = formatDistance(show.distance_km, show.distance_exact !== false);
    return (
      <div
        key={show.event_id || show.show_id}
        className="relative flex w-[270px] shrink-0 snap-start flex-col sm:w-[290px]"
      >
        {show.event_id && (
          <button
            type="button"
            onClick={() => wishlist.toggle(show.event_id)}
            aria-label={wishlist.has(show.event_id) ? "Remove from wishlist" : "Add to wishlist"}
            title={wishlist.has(show.event_id) ? "Remove from wishlist" : "Add to wishlist"}
            className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-lg backdrop-blur transition hover:scale-110 hover:bg-black/80"
          >
            {wishlist.has(show.event_id) ? "❤️" : "🤍"}
          </button>
        )}
        <Link
          href={show.event_id ? `/events/${show.event_id}` : `/shows/${show.show_id}`}
          draggable={false}
          className="group flex-1 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 transition hover:-translate-y-1 hover:border-blue-500/70 hover:shadow-xl hover:shadow-blue-950/30"
        >
          <div className="relative">
<<<<<<< HEAD
            <Poster
              src={show.poster_url}
              alt={`${show.title} poster`}
              className="h-64 w-full object-cover transition duration-300 group-hover:scale-[1.02]"
              fallbackClassName="flex h-64 items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950"
=======
            <EventPoster
              src={show.poster_url}
              alt={`${show.title} poster`}
              eventType={show.event_type}
              className="h-64 w-full object-cover transition duration-300 group-hover:scale-[1.02]"
              placeholderClassName="flex h-64 items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950"
>>>>>>> origin/main
            />
            {away && (
              <span
                title={
                  show.distance_exact === false
                    ? `This venue's exact spot isn't pinned yet, so the distance is measured to the centre of ${show.city}`
                    : "Straight-line distance from your location"
                }
                className="absolute bottom-3 left-3 rounded-full bg-black/75 px-2.5 py-1 text-xs font-semibold text-emerald-300 backdrop-blur"
              >
                📍 {away}
              </span>
            )}
          </div>

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

            <p className="mt-2 text-sm font-medium">
              {hasRating(show) ? (
                <span className="text-amber-400">
                  ★ {Number(show.avg_rating).toFixed(1)}
                  <span className="font-normal text-slate-400">
                    {" "}
                    · {show.review_count} {Number(show.review_count) === 1 ? "review" : "reviews"}
                  </span>
                </span>
              ) : (
                <span className="font-normal text-slate-500">★ No ratings yet</span>
              )}
            </p>

            <p className="mt-3 text-sm text-slate-300">
              <span aria-hidden="true">📍 </span>
              {`${show.venue_name || "Venue"}${show.city ? `, ${show.city}` : ""}`}
            </p>
            {show.theatres_count && show.theatres_count > 1 ? (
              <p className="mt-0.5 text-xs text-slate-400">
                + {show.theatres_count - 1} more {show.theatres_count - 1 === 1 ? "theatre" : "theatres"} nearby
              </p>
            ) : null}
            <p className="mt-1 text-sm text-slate-400">
              <span aria-hidden="true">◷ </span>
              {show.shows_count && show.shows_count > 1
                ? `${show.shows_count} Showtimes Available`
                : formatTime(show.start_time)}
            </p>

            <div className="mt-5 flex items-center justify-between border-t border-slate-800 pt-4">
              <span className="flex flex-col">
                <span className="flex items-baseline gap-2">
                  <span className="text-lg font-bold text-blue-400">
                    {show.shows_count && show.shows_count > 1 ? "From " : ""}₹{show.current_price ?? show.base_price ?? "—"}
                  </span>
                  {show.price_change_pct ? (
                    <span className="text-xs text-slate-500 line-through">₹{show.base_price}</span>
                  ) : null}
                </span>
                {show.pricing_reasons?.length ? (
                  <span
                    className={`text-xs font-medium ${
                      show.price_change_pct > 0 ? "text-amber-400" : show.price_change_pct < 0 ? "text-emerald-400" : "text-slate-400"
                    }`}
                  >
                    ⚡ {show.pricing_reasons.join(" · ")}
                  </span>
                ) : null}
              </span>
              <span
                className={`text-sm font-medium ${
                  (show.available_seats ?? 0) > 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {show.available_seats ?? "—"} seats
              </span>
            </div>
          </div>
        </Link>

        <div className="px-1 pb-2 pt-3">
          {show.event_id ? (
            <Link
              href={`/events/${show.event_id}/reviews`}
              draggable={false}
              className="inline-flex items-center rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-sm font-medium text-blue-300 transition hover:border-blue-400 hover:bg-blue-500/20"
            >
              ★ Reviews &amp; Ratings
            </Link>
          ) : (
            <span className="text-xs text-slate-500">Reviews unavailable for this show</span>
          )}
        </div>
      </div>
    );
  };

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
            Shows within {NEARBY_RADIUS_KM} km of you, plus every concert. Search by movie, venue, genre, or language.
          </p>
        </div>

        {/* Your location (same picker as the navbar) */}
        <button
          type="button"
          onClick={openPicker}
          className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-left transition hover:border-blue-500 sm:w-64"
        >
          <span className="min-w-0">
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Your location
            </span>
            <span className="block truncate text-sm font-semibold text-white">
              📍 {location ? location.label : "Set your location"}
            </span>
          </span>
          <span className="text-xs text-blue-400">Change</span>
        </button>
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
                              <EventPoster
                                src={show.poster_url}
                                alt={show.title}
                                eventType={show.event_type}
                                className="h-10 w-8 shrink-0 rounded object-cover"
                                placeholderClassName="flex h-10 w-8 shrink-0 items-center justify-center rounded bg-slate-800"
                                iconClassName="text-sm"
                              />
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-semibold text-white">
                                  {show.title}
                                </p>
                                <p className="truncate text-xs text-slate-400">
                                  {show.venue_name} • {show.city} • ₹{show.current_price ?? show.base_price ?? "—"}
                                </p>
                              </div>
                            </button>

                            <Link
                              href={`/shows/${show.show_id}`}
                              onClick={() => {
                                saveRecentSearch(show.title);
                                setDropdownOpen(false);
                              }}
                              className="shrink-0 rounded-lg bg-blue-600/20 px-2.5 py-1 text-xs font-medium text-blue-400 hover:bg-blue-600 hover:text-white"
                            >
                              View
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
            <option value="distance_asc">Sort: Nearest First</option>
            <option value="time_asc">Sort: Soonest First</option>
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
            <option value="seats_desc">Most Seats Available</option>
            <option value="rating_desc">Top Rated</option>
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
              : location
              ? `Now showing near ${location.label}`
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

      {/* No location yet: only concerts are listed until one is chosen */}
      {locationReady && !location && (
        <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-12 text-center">
          <p className="mb-3 text-4xl" aria-hidden="true">
            📍
          </p>
          <p className="font-semibold text-white">Choose your location</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-slate-400">
            Movies, theatre and other shows are listed within {NEARBY_RADIUS_KM} km of you. Set your
            location on the map or use your current location. Concerts are always shown below.
          </p>
          <button type="button" onClick={openPicker} className="btn-primary mt-5">
            Set my location
          </button>
        </div>
      )}

      {!locationReady ? null : loading ? (
        <div className="flex gap-4 overflow-hidden">
          {[1, 2, 3, 4, 5].map((n) => (
            <div
              key={n}
              className="h-96 w-[270px] shrink-0 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/60 sm:w-[290px]"
            />
          ))}
        </div>
      ) : shows.length === 0 ? (
        !location ? null : (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-16 text-center">
          <p className="mb-3 text-4xl" aria-hidden="true">
            🎬
          </p>
          <p className="font-semibold text-white">
            {activeFilterCount > 0
              ? "No shows matched your search"
              : `No shows within ${NEARBY_RADIUS_KM} km of ${location?.label ?? "you"}`}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            {activeFilterCount > 0
              ? "Try clearing some filters or searching for another title or venue."
              : "Try a different location, or check back soon."}
          </p>
          <div className="mt-4 flex justify-center gap-3">
            {activeFilterCount > 0 && (
              <button type="button" onClick={resetAllFilters} className="btn-primary">
                Reset All Filters
              </button>
            )}
            <button type="button" onClick={openPicker} className="btn-secondary">
              Change location
            </button>
          </div>
        </div>
        )
      ) : (
        <>
          {(filters.search.trim() || filters.event_type
            ? [{ key: "all", title: filters.search.trim() ? "Search results" : filters.event_type === "concert" ? "🎵 All concerts" : "Near you", items: shows }]
            : SECTIONS.map((sec) => ({
                key: sec.type,
                title: sec.title,
                items: shows.filter((x) =>
                  sec.type === "other"
                    ? !["movie", "concert", "theatre"].includes(String(x.event_type))
                    : String(x.event_type) === sec.type
                ),
              }))
          )
            .filter((row) => row.items.length > 0)
            .map((row) => (
              <ShowCarousel key={row.key} title={row.title} count={row.items.length}>
                {row.items.map((show) => renderCard(show))}
              </ShowCarousel>
            ))}
        </>
      )}
    </div>
  );
}