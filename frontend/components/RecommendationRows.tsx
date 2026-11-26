"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import EventPoster from "@/components/EventPoster";
import { useAuth } from "@/contexts/AuthContext";
import { useLocation } from "@/contexts/LocationContext";
import {
  recommendationsApi,
  type RecommendationsResponse,
  type RecommendedEvent,
} from "@/lib/api";

function formatShowTime(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function EventCard({ event, showReason }: { event: RecommendedEvent; showReason: boolean }) {
  const when = formatShowTime(event.next_show_time);
  const tags = event.match ?? [];
  return (
    <Link
      href={event.link}
      data-testid="recommendation-card"
      className="group flex w-56 shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 transition hover:-translate-y-1 hover:border-blue-500/70"
    >
      <EventPoster
        src={event.poster_url}
        alt={`${event.title} poster`}
        eventType={event.event_type}
        className="h-72 w-full object-cover"
        placeholderClassName="flex h-72 items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950"
        iconClassName="text-5xl"
      />
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <h3 className="line-clamp-2 font-semibold text-white group-hover:text-blue-400">{event.title}</h3>
        <p className="text-xs capitalize text-slate-400">
          {[event.event_type, event.genre].filter(Boolean).join(" • ")}
        </p>
        {showReason && event.reason ? (
          <p className="text-xs italic text-blue-200" data-testid="recommendation-reason">
            ✨ {event.reason}
          </p>
        ) : (
          tags.length > 0 && <p className="text-xs text-blue-200">{tags[0]}</p>
        )}
        {event.recent_bookings ? (
          <p className="text-xs text-orange-300">🔥 {event.recent_bookings} booked in the last 2 weeks</p>
        ) : null}
        <div className="mt-auto pt-2 text-xs text-slate-400">
          {when && <p>{when}{event.city ? ` · ${event.city}` : ""}</p>}
          {event.price_from != null && (
            <p className="font-medium text-emerald-300">From ₹{Math.round(event.price_from)}</p>
          )}
        </div>
      </div>
    </Link>
  );
}

function Row({
  title,
  subtitle,
  events,
  showReason = false,
  testId,
}: {
  title: string;
  subtitle?: string;
  events: RecommendedEvent[];
  showReason?: boolean;
  testId: string;
}) {
  if (events.length === 0) return null;
  return (
    <section className="mx-auto w-full max-w-6xl px-6 py-6" data-testid={testId}>
      <div className="mb-3">
        <h2 className="text-xl font-bold text-white">{title}</h2>
        {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex snap-x gap-4 overflow-x-auto pb-3">
        {events.map((e) => (
          <EventCard key={e.event_id} event={e} showReason={showReason} />
        ))}
      </div>
    </section>
  );
}

/** "Recommended for you" and "Trending" rows on the home page (#218). */
export default function RecommendationRows() {
  const { user, loading: authLoading } = useAuth();
  const { location, ready } = useLocation();
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const lat = location?.lat;
  const lng = location?.lng;
  const uid = user?.uid;

  useEffect(() => {
    if (authLoading || !ready) return;
    let active = true;
    setLoading(true);
    recommendationsApi
      .get(lat != null && lng != null ? { lat, lng } : null)
      .then((res) => active && setData(res))
      .catch(() => active && setData(null)) // the rest of the home page still works
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [authLoading, ready, uid, lat, lng]);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-6xl px-6 py-6" aria-busy="true">
        <div className="mb-3 h-6 w-48 animate-pulse rounded bg-slate-800" />
        <div className="flex gap-4 overflow-hidden">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-96 w-56 shrink-0 animate-pulse rounded-2xl bg-slate-900" />
          ))}
        </div>
      </div>
    );
  }
  if (!data) return null;

  const basedOn = data.based_on.length ? `Based on ${data.based_on.join(", ")}` : undefined;
  const trendingTitle = location ? `Trending near ${location.label}` : "Trending now";

  return (
    <div className="bg-[var(--background)] py-4">
      {data.personalized && (
        <Row
          title="Recommended for you"
          subtitle={basedOn}
          events={data.recommended}
          showReason={data.ai_reasons}
          testId="recommended-row"
        />
      )}
      {user && data.fallback === "no_history" && (
        <div className="mx-auto w-full max-w-6xl px-6 pt-4" data-testid="preferences-hint">
          <p className="rounded-xl border border-blue-900/60 bg-blue-950/30 px-4 py-3 text-sm text-blue-100">
            Want picks made for you?{" "}
            <Link href="/profile#preferences" className="font-semibold text-blue-400 underline">
              Tell us your favourite genres, artists and cities
            </Link>
            , or book and save a few events.
          </p>
        </div>
      )}
      <Row
        title={trendingTitle}
        subtitle={
          data.trending.some((e) => e.recent_bookings)
            ? "Most booked in the last two weeks"
            : "Top rated and coming up soon"
        }
        events={data.trending}
        testId="trending-row"
      />
    </div>
  );
}
