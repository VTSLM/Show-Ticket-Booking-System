"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useWishlist } from "@/components/useWishlist";
import EventPoster from "@/components/EventPoster";
import { bookingsApi } from "@/lib/api";
import { useLocation } from "@/contexts/LocationContext";
import { formatDistance, haversineKm } from "@/lib/geo";
import { googleMapsUrl } from "@/lib/maps";
import { addRecentlyViewed } from "@/lib/recentlyViewed";
import ScrollTabs from "@/components/ScrollTabs";

interface ShowDetailsProps {
  showData: any;
  preselectedShowId?: string;
  isEventMode?: boolean;
}

/** The cinema format a screen offers, read from its name ("IMAX Audi 2" -> "IMAX 3D"). */
function screenFormat(screenName?: string | null): string {
  const name = (screenName || "").toLowerCase();
  if (name.includes("imax")) return "IMAX 3D";
  if (name.includes("4d")) return "4DX 3D";
  if (name.includes("3d")) return "3D";
  return "2D";
}

export default function ShowDetailsView({
  showData,
  preselectedShowId,
  isEventMode = false,
}: ShowDetailsProps) {
  const router = useRouter();
  const [selectedShowId, setSelectedShowId] = useState<string>(
    preselectedShowId || (showData?.upcoming_shows?.[0]?.show_id ?? showData?.show_id ?? "")
  );
  const [selectedDateFilter, setSelectedDateFilter] = useState<string>("all");
  const [selectedFormat, setSelectedFormat] = useState<string>("all");
  const [isFormatModalOpen, setIsFormatModalOpen] = useState<boolean>(false);
  const [copied, setCopied] = useState(false);
  const [waitlistPositions, setWaitlistPositions] = useState<Record<string, number>>({});
  const [waitlistLoadingId, setWaitlistLoadingId] = useState<string | null>(null);
  const wishlist = useWishlist();
  const { location } = useLocation();

  useEffect(() => {
    bookingsApi.myWaitlist()
      .then((entries) => {
        const positions: Record<string, number> = {};
        entries.forEach((entry: any) => {
          positions[entry.show_id] = Number(entry.position);
        });
        setWaitlistPositions(positions);
      })
      .catch(() => {
        // Guests and signed-out users simply see the normal booking controls.
      });
  }, []);

  // Remember this show for the "Recently viewed" row on the Browse page
  useEffect(() => {
    if (!showData) return;
    addRecentlyViewed({
      event_id: showData.event_id || (isEventMode ? showData.id : null) || null,
      show_id: isEventMode ? null : showData.show_id || null,
      title: showData.title,
      poster_url: showData.poster_url || null,
      event_type: showData.event_type || null,
      language: showData.language || null,
      genre: showData.genre || null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showData?.event_id, showData?.id, showData?.show_id, showData?.title, isEventMode]);

  const handleJoinWaitlist = async (showId: string) => {
    if (!showId || waitlistLoadingId) return;
    setWaitlistLoadingId(showId);
    try {
      const result = await bookingsApi.joinWaitlist(showId);
      setWaitlistPositions((current) => ({
        ...current,
        [showId]: result.position,
      }));
      toast.success(
        result.status === "already_joined"
          ? `You are already on the waitlist (position ${result.position}).`
          : `Added to waitlist. Your position is ${result.position}.`
      );
    } catch (error: any) {
      if (error?.message === "Not authenticated") {
        toast.error("Please log in to join the waitlist.");
        router.push("/auth/login");
      } else {
        toast.error(error?.message || "Could not join the waitlist.");
      }
    } finally {
      setWaitlistLoadingId(null);
    }
  };

  const handleLeaveWaitlist = async (showId: string) => {
    if (!showId || waitlistLoadingId) return;
    setWaitlistLoadingId(showId);
    try {
      await bookingsApi.leaveWaitlist(showId);
      setWaitlistPositions((current) => {
        const next = { ...current };
        delete next[showId];
        return next;
      });
      toast.success("You have left the waitlist.");
    } catch (error: any) {
      toast.error(error?.message || "Could not leave the waitlist.");
    } finally {
      setWaitlistLoadingId(null);
    }
  };

  // Upcoming shows and distinct cities
  const upcomingShows: any[] = Array.isArray(showData?.upcoming_shows) ? showData.upcoming_shows : [];
  // The user's own city (from the location picker) comes first, the rest alphabetically
  const { location: userLocation, ready: locationReady } = useLocation();
  const homeCity = location?.label ? location.label.replace(/^Near /, "") : null;
  const uniqueCities: string[] = (
    Array.from(new Set(upcomingShows.map((s: any) => s.city).filter(Boolean))) as string[]
  ).sort((a, b) => (a === homeCity ? -1 : b === homeCity ? 1 : a.localeCompare(b)));
  const hasHomeCity = homeCity !== null && uniqueCities.includes(homeCity);
  // A show picked on an earlier page keeps its own city
  const preselectedCity: string | undefined = preselectedShowId
    ? upcomingShows.find((s: any) => s.show_id === preselectedShowId)?.city
    : undefined;

  const [selectedCity, setSelectedCity] = useState<string>(
    preselectedCity || uniqueCities[0] || showData?.city || "all"
  );
  const [cityChosen, setCityChosen] = useState(false);

  // The saved location is read after the first render, so switch to it once it is known
  useEffect(() => {
    if (locationReady && hasHomeCity && homeCity && !preselectedCity && !cityChosen) {
      setSelectedCity(homeCity);
    }
  }, [locationReady, hasHomeCity, homeCity, preselectedCity, cityChosen]);

  if (!showData) return null;

  const eventType = (showData.event_type || "movie").toLowerCase();
  // Cinema formats (2D, 3D, IMAX, 4DX) only exist for movies
  const isMovie = eventType === "movie";
  const title = showData.title || "Untitled Show";
  const backdrop = showData.backdrop_url || showData.poster_url;
  const poster = showData.poster_url;
  const eventId = showData.event_id || showData.id;
  // Wishlist works on events: use the real event id (never a show id)
  const wishEventId: string | null = showData.event_id || (isEventMode ? showData.id : null) || null;

  // Format date helper
  const formatDate = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return isoString;
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  const formatDuration = (mins?: number) => {
    if (!mins) return null;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    if (h > 0 && m > 0) return `${h}h ${m}m`;
    if (h > 0) return `${h}h`;
    return `${m}m`;
  };

  // Working Share Functionality (Web Share API + Clipboard Fallback)
  const handleShare = async () => {
    const shareUrl = typeof window !== "undefined" ? window.location.href : "";
    const shareData = {
      title: `${title} on TicketFlow`,
      text: `Book tickets for ${title} on TicketFlow!`,
      url: shareUrl,
    };

    if (navigator.share && navigator.canShare && navigator.canShare(shareData)) {
      try {
        await navigator.share(shareData);
        return;
      } catch (err: any) {
        if (err.name === "AbortError") return;
      }
    }

    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied to clipboard!");
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error("Could not copy link");
    }
  };

  // Movie formats. Non-movie events (concerts, comedy, theatre, other) have none.
  const eventFormats: string[] = !isMovie
    ? []
    : Array.isArray(showData.formats)
    ? showData.formats
    : typeof showData.formats === "string"
    ? [showData.formats]
    : [];

  // What the movie is actually showing in: derived from each showtime's screen
  const screenFormats: string[] = isMovie ? upcomingShows.map((s: any) => screenFormat(s.screen_name)) : [];

  // Shown next to the title: the movie's formats plus any its showtimes use
  const availableFormats: string[] = Array.from(new Set([...eventFormats, ...screenFormats])).filter(Boolean);
  // Offered as filters and in the booking pop-up: only formats with a showtime
  const bookableFormats: string[] = Array.from(new Set(screenFormats));
  const offerFormatChoice = isMovie && bookableFormats.length > 1;

  // Book Tickets CTA handler (opens language & format selector modal)
  const handleBookTickets = () => {
    if (upcomingShows.length > 0 && offerFormatChoice) {
      setIsFormatModalOpen(true);
    } else if (upcomingShows.length > 0) {
      document.getElementById("showtimes-section")?.scrollIntoView({ behavior: "smooth" });
    } else if (showData.show_id) {
      router.push(`/shows/${showData.show_id}/seats`);
    } else {
      toast.error("No scheduled showtimes available for booking right now.");
    }
  };

  // Handle format choice from modal
  const handleSelectFormatAndScroll = (fmt: string) => {
    setSelectedFormat(fmt);
    setIsFormatModalOpen(false);
    setTimeout(() => {
      document.getElementById("showtimes-section")?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  };

  // Upcoming shows list filtered by City and Date and Screen Format
  const cityFilteredShows = upcomingShows.filter((s: any) => {
    if (selectedCity === "all") return true;
    return s.city === selectedCity;
  });

  const uniqueDates: string[] = Array.from(
    new Set(
      cityFilteredShows
        .map((s: any) => {
          try {
            return new Date(s.start_time).toISOString().split("T")[0];
          } catch {
            return "";
          }
        })
        .filter(Boolean)
    )
  );

  const activeDate =
    selectedDateFilter !== "all" && uniqueDates.includes(selectedDateFilter)
      ? selectedDateFilter
      : uniqueDates[0] || "all";

  const dateAndCityFilteredShows = cityFilteredShows.filter((s: any) => {
    if (activeDate !== "all") {
      try {
        const d = new Date(s.start_time).toISOString().split("T")[0];
        if (d !== activeDate) return false;
      } catch {
        return true;
      }
    }
    if (offerFormatChoice && selectedFormat !== "all" && screenFormat(s.screen_name) !== selectedFormat) {
      return false;
    }
    return true;
  });

  // Group by Theatre / Venue
  const theatreMap = new Map<string, { venue_name: string; address?: string; city?: string; latitude?: number | null; longitude?: number | null; shows: any[] }>();
  dateAndCityFilteredShows.forEach((s: any) => {
    const key = s.venue_id || s.venue_name;
    if (!theatreMap.has(key)) {
      theatreMap.set(key, {
        venue_name: s.venue_name,
        address: s.address,
        city: s.city,
        latitude: s.latitude,
        longitude: s.longitude,
        shows: [],
      });
    }
    theatreMap.get(key)!.shows.push(s);
  });
  const theatresList = Array.from(theatreMap.values());

  // Cast & crew / artists data (strictly real data)
  let rawCast = showData.cast_crew;
  if (typeof rawCast === "string") {
    try {
      rawCast = JSON.parse(rawCast);
    } catch {}
  }
  const castList = Array.isArray(rawCast) ? rawCast : [];
  const artistList = Array.isArray(showData.artists) ? showData.artists : [];
  const zonesList = Array.isArray(showData.zones) ? showData.zones : [];

  const minStartingPrice = upcomingShows.length > 0
    ? Math.min(...upcomingShows.map((s: any) => Number(s.base_price || 280)))
    : (showData.base_price || 280);

  const totalDistinctTheatres = Array.from(new Set(upcomingShows.map((s: any) => s.venue_name || s.venue_id))).length || 1;

  return (
    <div className="min-h-screen bg-[#090b12] text-[#f4f6fb]">
      {/* 1. Backdrop Hero Section */}
      <div className="relative w-full overflow-hidden border-b border-[#1b2030] bg-[#0c0f18]">
        {backdrop ? (
          <div
            className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-25 filter blur-sm scale-105"
            style={{ backgroundImage: `url(${backdrop})` }}
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-r from-blue-950/30 via-purple-950/20 to-slate-900" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#090b12] via-[#090b12]/70 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#090b12] via-transparent to-[#090b12]" />

        {/* Hero Content Container */}
        <div className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-14">
          <div className="flex flex-col gap-8 md:flex-row md:items-start md:gap-12">
            {/* Left: Poster Card */}
            <div className="mx-auto w-60 shrink-0 overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/90 shadow-2xl shadow-black/80 md:mx-0 md:w-72">
              <EventPoster
                src={poster}
                alt={`${title} poster`}
                eventType={eventType}
                className="aspect-[2/3] w-full object-cover transition-transform duration-300 hover:scale-[1.02]"
                placeholderClassName="flex aspect-[2/3] w-full items-center justify-center bg-slate-800"
              />
            </div>

            {/* Right: Event Information */}
            <div className="flex flex-1 flex-col justify-between">
              <div>
                {/* Event Type & Certification Pills */}
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-blue-500/40 bg-blue-500/10 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-blue-400">
                    {eventType}
                  </span>
                  {showData.certificate && (
                    <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-xs font-semibold text-slate-300">
                      {showData.certificate}
                    </span>
                  )}
                  {showData.genre && (
                    <span className="rounded-md border border-slate-700/60 bg-slate-800/40 px-2.5 py-0.5 text-xs text-slate-300">
                      {showData.genre}
                    </span>
                  )}
                </div>

                {/* Title */}
                <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl">
                  {title}
                </h1>

                {/* Rating & Review Section */}
                <div className="mt-4 flex flex-wrap items-center gap-4">
                  {showData.avg_rating ? (
                    <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2">
                      <span className="text-lg text-amber-400">★</span>
                      <span className="text-base font-bold text-white">
                        {showData.avg_rating}/10
                      </span>
                      <span className="text-xs text-slate-400">
                        ({showData.review_count || 0} reviews)
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs text-slate-400">
                      <span className="text-slate-500">★</span>
                      <span>No reviews yet</span>
                    </div>
                  )}

                  {eventId && (
                    <Link
                      href={`/events/${eventId}/reviews`}
                      className="rounded-xl border border-slate-700 bg-slate-800/70 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-blue-500 hover:bg-slate-800"
                    >
                      Rate &amp; Review
                    </Link>
                  )}

                  <button
                    type="button"
                    onClick={handleShare}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/70 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
                  >
                    <span>{copied ? "✓ Copied" : "↗ Share"}</span>
                  </button>

                  {wishEventId && (
                    <button
                      type="button"
                      onClick={() => wishlist.toggle(wishEventId)}
                      className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
                        wishlist.has(wishEventId)
                          ? "border-red-500/50 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                          : "border-slate-700 bg-slate-800/70 text-slate-200 hover:border-slate-500 hover:text-white"
                      }`}
                    >
                      <span>{wishlist.has(wishEventId) ? "❤️ Saved" : "🤍 Add to Wishlist"}</span>
                    </button>
                  )}
                </div>

                {/* Metadata Pills: Language, Duration, Formats */}
                <div className="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-300">
                  {showData.language && (
                    <div className="flex items-center gap-1 rounded-md bg-slate-800/60 px-2.5 py-1">
                      <span className="text-xs text-slate-400">Language:</span>
                      <span className="font-semibold">{showData.language}</span>
                    </div>
                  )}

                  {showData.duration_minutes ? (
                    <div className="flex items-center gap-1 rounded-md bg-slate-800/60 px-2.5 py-1">
                      <span className="text-xs text-slate-400">Duration:</span>
                      <span className="font-semibold">{formatDuration(showData.duration_minutes)}</span>
                    </div>
                  ) : null}

                  {showData.release_date && (
                    <div className="flex items-center gap-1 rounded-md bg-slate-800/60 px-2.5 py-1">
                      <span className="text-xs text-slate-400">Released:</span>
                      <span className="font-semibold">{formatDate(showData.release_date)}</span>
                    </div>
                  )}

                  {availableFormats.length > 0 && (
                    <div className="flex items-center gap-1.5">
                      {availableFormats.map((fmt: string) => (
                        <span
                          key={fmt}
                          className="rounded border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-slate-300"
                        >
                          {fmt}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Multi-theatre or Single Theatre Availability Banner */}
                {upcomingShows.length > 1 ? (
                  <div className="mt-6 rounded-xl border border-blue-900/50 bg-gradient-to-r from-blue-950/60 via-slate-900/80 to-purple-950/40 p-4 shadow-lg shadow-black/50">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                          <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
                            {isMovie ? "Now Showing Across Theatres" : "Happening Across Venues"}
                          </p>
                        </div>
                        <p className="mt-1 text-base font-bold text-white">
                          📍 In {totalDistinctTheatres} {isMovie ? "Theatre" : "Venue"}{totalDistinctTheatres === 1 ? "" : "s"} ({uniqueCities.length ? uniqueCities.join(", ") : "Available Cities"})
                        </p>
                        <p className="mt-0.5 text-xs text-slate-300">
                          🕒 {upcomingShows.length} Scheduled Showtimes Available
                        </p>
                      </div>

                      <div className="text-right">
                        <span className="text-xs text-slate-400">Tickets starting from</span>
                        <p className="text-xl font-extrabold text-emerald-400">
                          ₹{minStartingPrice}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : showData.venue_name ? (
                  <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                          Venue &amp; Scheduled Showtime
                        </p>
                        <p className="mt-1 text-base font-semibold text-white">
                          📍 {showData.venue_name}
                          {showData.city ? `, ${showData.city}` : ""}
                          {showData.screen_name ? ` — ${showData.screen_name}` : ""}
                        </p>
                        {location && showData.latitude != null && showData.longitude != null && (
                          <p className="mt-0.5 text-xs font-medium text-emerald-400">
                            📍 {formatDistance(haversineKm(location.lat, location.lng, showData.latitude, showData.longitude), true)}
                          </p>
                        )}
                        {googleMapsUrl(showData, location) && (
                          <a
                            href={googleMapsUrl(showData, location) as string}
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Open the route to this venue in Google Maps"
                            aria-label={`Open ${showData.venue_name} in Google Maps`}
                            className="mt-1 inline-flex items-center gap-1 rounded border border-blue-500/30 bg-blue-950/50 px-2 py-0.5 text-[11px] font-semibold text-blue-300 transition hover:border-blue-400 hover:bg-blue-900/50 hover:text-white"
                          >
                            🗺️ Google Maps ↗
                          </a>
                        )}
                        {showData.start_time && (
                          <p className="mt-0.5 text-xs text-blue-400">
                            🗓 {formatDate(showData.start_time)} at {formatTime(showData.start_time)}
                          </p>
                        )}
                      </div>

                      {showData.base_price && (
                        <div className="text-right">
                          <span className="text-xs text-slate-400">Starting from</span>
                          <p className="text-xl font-extrabold text-emerald-400">
                            ₹{showData.base_price}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}

                {/* Primary Booking CTA */}
                <div className="mt-7 flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    onClick={handleBookTickets}
                    className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-8 py-3.5 text-base font-bold text-white shadow-lg shadow-blue-600/30 transition hover:bg-blue-500 hover:shadow-blue-500/50 active:scale-95 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-[#090b12]"
                  >
                    🎟 Book Tickets
                  </button>

                  <Link
                    href="/browse"
                    className="rounded-xl border border-slate-700 bg-slate-800/50 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-slate-800 hover:text-white"
                  >
                    ← Back to Browse
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Main Content: About, Cast, Formats, and Theatres List */}
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
          {/* Main Column */}
          <div className="lg:col-span-2 space-y-10">
            {/* Description */}
            {showData.description && (
              <section className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
                <h2 className="text-xl font-bold text-white">About the Event</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-300">
                  {showData.description}
                </p>
              </section>
            )}

            {/* CAST & CREW CAROUSEL (Works dynamically for ANY movie or event) */}
            {castList.length > 0 && (
              <section className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-white">Cast</h2>
                  <span className="text-xs text-slate-400 font-medium">Principal Actors</span>
                </div>

                {/* Horizontal Cast Card Carousel */}
                <div className="mt-4 flex gap-4 overflow-x-auto pb-3 pt-1 scrollbar-thin scrollbar-thumb-slate-700">
                  {castList
                    .filter((m: any) => !["Director", "Producer", "Music Composer"].includes(m.role))
                    .map((member: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex w-36 shrink-0 flex-col items-center rounded-xl border border-slate-800/80 bg-slate-900/60 p-3.5 text-center transition hover:border-slate-700 hover:bg-slate-900"
                      >
                        <div className="relative h-20 w-20 overflow-hidden rounded-full border-2 border-slate-700/80 shadow-md">
                          {member.image_url ? (
                            <img
                              src={member.image_url}
                              alt={member.name}
                              className="h-full w-full object-cover"
                              onError={(e) => {
                                const target = e.currentTarget;
                                target.style.display = "none";
                                const parent = target.parentElement;
                                if (parent) {
                                  const fallback = document.createElement("div");
                                  fallback.className =
                                    "flex h-full w-full items-center justify-center bg-blue-950/80 font-bold text-blue-400 text-lg";
                                  fallback.innerText = member.name ? member.name.charAt(0) : "👤";
                                  parent.appendChild(fallback);
                                }
                              }}
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center bg-blue-950/80 font-bold text-blue-400 text-lg">
                              {member.name ? member.name.charAt(0) : "👤"}
                            </div>
                          )}
                        </div>
                        <p className="mt-2.5 text-xs font-bold text-white line-clamp-1">{member.name}</p>
                        <p className="mt-0.5 text-[11px] font-semibold text-blue-400 line-clamp-1">
                          {member.character || member.role || "Cast"}
                        </p>
                      </div>
                    ))}
                </div>

                {/* Production Crew Section (Director, Producers, Music) */}
                {castList.some((m: any) => ["Director", "Producer", "Music Composer"].includes(m.role)) && (
                  <div className="mt-6 border-t border-slate-800/80 pt-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Key Crew &amp; Production
                    </h3>
                    <div className="mt-3 flex flex-wrap gap-3">
                      {castList
                        .filter((m: any) => ["Director", "Producer", "Music Composer"].includes(m.role))
                        .map((crew: any, cIdx: number) => (
                          <div
                            key={cIdx}
                            className="rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs"
                          >
                            <span className="font-semibold text-white">{crew.name}</span>
                            <span className="ml-1.5 text-slate-400 font-medium">({crew.role})</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* ARTISTS & LINEUP (Concerts & Festivals) */}
            {eventType === "concert" && (
              <section className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
                <h2 className="text-xl font-bold text-white">Artists &amp; Lineup</h2>
                {artistList.length > 0 ? (
                  <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                    {artistList.map((artist: any, idx: number) => (
                      <div
                        key={idx}
                        className="flex flex-col items-center rounded-xl border border-slate-800/70 bg-slate-900/60 p-4 text-center"
                      >
                        {artist.image_url ? (
                          <img
                            src={artist.image_url}
                            alt={artist.name}
                            className="h-20 w-20 rounded-full object-cover border-2 border-purple-500/40"
                          />
                        ) : (
                          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-purple-950/60 text-2xl text-purple-400 border border-purple-800/50">
                            🎤
                          </div>
                        )}
                        <p className="mt-2 font-bold text-white">{artist.name}</p>
                        <p className="text-xs text-purple-300">{artist.genre || "Headliner"}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-400">
                    Featuring premier live performances. Check back for final setlist announcements.
                  </p>
                )}

                {zonesList.length > 0 && (
                  <div className="mt-6 border-t border-slate-800 pt-5">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                      Available Passes &amp; Zones
                    </h3>
                    <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                      {zonesList.map((z: any) => (
                        <div
                          key={z.id}
                          className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/40 p-3"
                        >
                          <div>
                            <p className="font-semibold text-white">{z.name}</p>
                            <span className="text-xs text-slate-400 capitalize">
                              {z.zone_type || "Standing"} • {z.available_capacity ?? z.total_capacity} passes left
                            </span>
                          </div>
                          <span className="text-sm font-bold text-emerald-400">
                            ₹{z.price}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* BOOKMYSHOW-STYLE THEATRES & SHOWTIMES DIRECTORY (SCREENSHOT 4) */}
            {upcomingShows.length > 0 && (
              <section id="showtimes-section" className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
                {/* Event Title Header with Tags */}
                <div className="border-b border-slate-800/80 pb-5">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <h2 className="text-2xl font-extrabold text-white">
                        {title} — ({showData.language || "Hindi"})
                      </h2>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        {showData.duration_minutes && (
                          <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-slate-300 font-medium">
                            {isMovie ? "Movie runtime" : "Duration"}: {formatDuration(showData.duration_minutes)}
                          </span>
                        )}
                        {showData.certificate && (
                          <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2 py-1 text-slate-300 font-bold">
                            {showData.certificate}
                          </span>
                        )}
                        {showData.genre && (
                          <span className="rounded-md border border-slate-700/60 bg-slate-800/40 px-2.5 py-1 text-slate-300">
                            {showData.genre}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* City Selector */}
{uniqueCities.length > 0 && (
  <div
    className="flex min-w-0 max-w-full items-center gap-2"
    data-testid="city-picker"
  >
    <span className="shrink-0 text-xs font-semibold text-slate-400">
      City:
    </span>

    <ScrollTabs activeKey={selectedCity} label="cities">
      {uniqueCities.map((c) => (
        <button
          key={c}
          type="button"
          data-active={selectedCity === c}
          aria-pressed={selectedCity === c}
          onClick={() => {
            setSelectedCity(c);
            setCityChosen(true);
            setSelectedDateFilter("all");
          }}
          className={`shrink-0 whitespace-nowrap rounded-md px-3 py-1 text-xs font-semibold transition ${
            selectedCity === c
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-300 hover:bg-slate-800"
          }`}
        >
          📍 {c}
        </button>
      ))}
    </ScrollTabs>
  </div>
)}
                  </div>
                </div>

                {/* Horizontal Date Selector Bar (Screenshot 4) */}
                {uniqueDates.length > 0 && (
                  <div className="mt-5 flex items-center gap-2 overflow-x-auto pb-3 border-b border-slate-800/80 scrollbar-thin scrollbar-thumb-slate-700">
                    {uniqueDates.map((d) => {
                      const isSelected = activeDate === d;
                      const dateObj = new Date(d);
                      const dayName = dateObj.toLocaleDateString("en-IN", { weekday: "short" });
                      const dayNum = dateObj.toLocaleDateString("en-IN", { day: "numeric" });
                      const monthName = dateObj.toLocaleDateString("en-IN", { month: "short" });

                      return (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setSelectedDateFilter(d)}
                          className={`flex flex-col items-center rounded-xl border px-4 py-2 text-xs font-semibold transition shrink-0 ${
                            isSelected
                              ? "border-rose-500 bg-rose-600 text-white shadow-md shadow-rose-600/30"
                              : "border-slate-800 bg-slate-900/80 text-slate-300 hover:border-slate-700 hover:bg-slate-800"
                          }`}
                        >
                          <span className={`text-[10px] uppercase font-bold ${isSelected ? "text-rose-100" : "text-slate-400"}`}>
                            {dayName}
                          </span>
                          <span className="text-lg font-extrabold leading-tight">
                            {dayNum}
                          </span>
                          <span className={`text-[10px] ${isSelected ? "text-rose-200" : "text-slate-400"}`}>
                            {monthName}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Filters Bar: Format Selector (movies with more than one format) + Legend */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-4 py-2">
                  {offerFormatChoice ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider mr-1">
                      Format:
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedFormat("all")}
                      className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                        selectedFormat === "all"
                          ? "border border-rose-500 bg-rose-500/10 text-rose-400"
                          : "border border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-white"
                      }`}
                    >
                      All Formats
                    </button>
                    {bookableFormats.map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => setSelectedFormat(fmt)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                          selectedFormat === fmt
                            ? "border border-rose-500 bg-rose-500/10 text-rose-400"
                            : "border border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:text-white"
                        }`}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                  ) : (
                    <span />
                  )}

                  <div className="flex items-center gap-3 text-[11px] text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      AVAILABLE
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-amber-400" />
                      FAST FILLING
                    </span>
                  </div>
                </div>

                {/* Theatres and Showtimes Grouped List (Screenshot 4) */}
                <div className="mt-6 space-y-5">
                  {theatresList.length === 0 ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center text-sm text-slate-400">
                      <p className="text-base font-semibold text-slate-300">No shows found for the selected filter</p>
                      <p className="mt-1 text-xs">
                        {offerFormatChoice ? "Try selecting a different date or screen format." : "Try selecting a different date."}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedDateFilter("all");
                          setSelectedFormat("all");
                        }}
                        className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-500"
                      >
                        Reset Filters
                      </button>
                    </div>
                  ) : (
                    theatresList.map((theatre, tIdx) => (
                      <div
                        key={tIdx}
                        className="rounded-xl border border-slate-800/90 bg-slate-900/70 p-5 transition hover:border-slate-700/90"
                      >
                        {/* Cinema Header */}
                        <div className="mb-4 flex flex-wrap items-start justify-between gap-2 border-b border-slate-800/60 pb-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="text-base font-bold text-white">
                                📍 {theatre.venue_name}
                              </h3>
                              {theatre.city && (
                                <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-semibold text-slate-300">
                                  {theatre.city}
                                </span>
                              )}
                              {location && theatre.latitude != null && theatre.longitude != null && (
                                <span className="rounded bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                                  📍 {formatDistance(haversineKm(location.lat, location.lng, theatre.latitude, theatre.longitude), true)}
                                </span>
                              )}
                              {(() => {
                                const mapsHref = googleMapsUrl(theatre, location);
                                return mapsHref ? (
                                  <a
                                    href={mapsHref}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title="Open the route to this cinema in Google Maps"
                                    aria-label={`Open ${theatre.venue_name} in Google Maps`}
                                    className="inline-flex items-center gap-1 rounded border border-blue-500/30 bg-blue-950/50 px-2 py-0.5 text-[11px] font-semibold text-blue-300 transition hover:border-blue-400 hover:bg-blue-900/50 hover:text-white"
                                  >
                                    🗺️ Google Maps ↗
                                  </a>
                                ) : null;
                              })()}
                              <span className="text-[11px] text-emerald-400 font-medium">
                                • Cancellation Available
                              </span>
                            </div>
                            {theatre.address && (
                              <p className="mt-0.5 text-xs text-slate-400">{theatre.address}</p>
                            )}
                          </div>
                        </div>

                        {/* Showtimes Grid for this Cinema */}
                        <div className="flex flex-wrap items-center gap-3.5">
                          {theatre.shows.map((s: any) => {
                            const availCount = s.available_seats ?? 0;
                            const isAvail = availCount > 0;
                            const isFastFilling = availCount > 0 && availCount <= 25;

                            return isAvail ? (
                                <Link
                                  key={s.show_id}
                                  href={`/shows/${s.show_id}/seats`}
                                  className={`group flex flex-col items-center justify-center rounded-xl border px-5 py-3 transition active:scale-95 ${
                                    isFastFilling
                                      ? "border-amber-500/40 bg-slate-900/90 hover:border-amber-400 hover:bg-amber-950/20"
                                      : "border-slate-700/80 bg-slate-900 hover:border-blue-500 hover:bg-blue-950/30 hover:shadow-lg"
                                  }`}
                                >
                                  <span className="text-base font-extrabold text-white group-hover:text-blue-400">
                                    {formatTime(s.start_time)}
                                  </span>
                                  <div className="mt-1 flex items-center gap-1.5 text-[11px]">
                                  <span className="font-bold text-slate-300 uppercase">
                                    {s.screen_name || (isMovie ? "2D" : "Stage")}
                                  </span>
                                  <span className="text-slate-600">•</span>
                                  <span className="font-extrabold text-emerald-400">
                                    ₹{s.base_price}
                                  </span>
                                </div>
                                <span
                                  className={`mt-1 flex items-center gap-1 text-[10px] font-bold ${
                                    isFastFilling
                                      ? "text-amber-400"
                                      : "text-emerald-400"
                                  }`}
                                >
                                  <span
                                    className={`h-1.5 w-1.5 rounded-full ${
                                      isFastFilling
                                        ? "bg-amber-400"
                                        : "bg-emerald-400"
                                    }`}
                                  />
                                  {isFastFilling ? "FAST FILLING" : "AVAILABLE"}
                                  </span>
                                </Link>
                              ) : (
                                <button
                                  key={s.show_id}
                                  type="button"
                                  onClick={() =>
                                    waitlistPositions[s.show_id] !== undefined
                                      ? handleLeaveWaitlist(s.show_id)
                                      : handleJoinWaitlist(s.show_id)
                                  }
                                  disabled={waitlistLoadingId === s.show_id}
                                  className="group flex flex-col items-center justify-center rounded-xl border border-slate-700 bg-slate-950/70 px-5 py-3 transition hover:border-purple-500 hover:bg-purple-950/20 disabled:cursor-not-allowed disabled:opacity-70"
                                >
                                  <span className="text-base font-extrabold text-white">
                                    {formatTime(s.start_time)}
                                  </span>
                                  <span className="mt-1 text-[11px] font-bold text-purple-300">
                                    {waitlistLoadingId === s.show_id
                                      ? "Please wait..."
                                      : waitlistPositions[s.show_id] !== undefined
                                      ? `Waitlist #${waitlistPositions[s.show_id]}`
                                      : "Join Waitlist"}
                                  </span>
                                  {waitlistPositions[s.show_id] !== undefined &&
                                    waitlistLoadingId !== s.show_id && (
                                      <span className="mt-0.5 text-[10px] text-slate-400 group-hover:text-red-400">
                                        Click to leave
                                      </span>
                                    )}
                                </button>
                              );
                          })}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            )}
          </div>

          {/* Sidebar Column: Terms & Conditions Preview & Venue Overview */}
          <div className="space-y-6">
            {/* Show-Specific Terms & Conditions Preview */}
            <section className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-white">Terms &amp; Conditions</h3>
                <span className="text-xs text-slate-400">
                  {showData.is_default_terms ? "Platform Standard" : "Show Specific"}
                </span>
              </div>
              <div className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-slate-800/80 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-400">
                <p className="whitespace-pre-line">
                  {showData.terms_and_conditions || "Standard TicketFlow terms apply. Valid ID required for entry."}
                </p>
              </div>
              <p className="mt-2 text-[11px] text-slate-500">
                You will be requested to formally review and accept these terms before proceeding to payment.
              </p>
            </section>

            {/* Organizer Profile Information */}
            {showData.organizer_name && (
              <section className="rounded-2xl border border-slate-800 bg-[#0e121d] p-6 shadow-sm">
                <h3 className="font-bold text-white">Presented By</h3>
                <p className="mt-1 text-sm font-semibold text-slate-200">
                  {showData.organizer_name}
                </p>
                <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs text-emerald-400 font-medium">
                  <span>✓</span> Verified Event Organizer
                </div>
              </section>
            )}
          </div>
        </div>
      </div>

      {/* SELECT LANGUAGE AND FORMAT MODAL (SCREENSHOT 3) */}
      {isFormatModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-700 bg-[#0f1422] p-6 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h3 className="text-lg font-bold text-white">Select language and format</h3>
              <button
                type="button"
                onClick={() => setIsFormatModalOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Language Label */}
            <div className="mt-4">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {(showData.language || "Hindi").toUpperCase()}
              </span>

              {/* Format Pills (Matching screenshot 3) */}
              <div className="mt-3 flex flex-wrap items-center gap-2.5">
                {bookableFormats.map((fmt) => (
                  <button
                    key={fmt}
                    type="button"
                    onClick={() => handleSelectFormatAndScroll(fmt)}
                    className="rounded-full border border-rose-500/70 bg-transparent px-5 py-2 text-sm font-bold text-rose-400 transition hover:bg-rose-500 hover:text-white active:scale-95 shadow-sm"
                  >
                    {fmt}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => handleSelectFormatAndScroll("all")}
                  className="rounded-full border border-slate-600 bg-slate-800 px-5 py-2 text-sm font-bold text-slate-200 transition hover:bg-slate-700 hover:text-white active:scale-95"
                >
                  Select all
                </button>
              </div>
            </div>

            <div className="mt-6 border-t border-slate-800 pt-3 text-right">
              <button
                type="button"
                onClick={() => handleSelectFormatAndScroll("all")}
                className="text-xs font-semibold text-blue-400 hover:underline"
              >
                Skip and view all cinemas →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
