"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { wishlistApi } from "@/lib/api";
import { useLocation } from "@/contexts/LocationContext";
import { formatDistance, haversineKm } from "@/lib/geo";

const fmt = (d: string) =>
  new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

function WishPoster({ src, alt }: { src?: string | null; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className="flex h-56 items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950">
        <span className="text-5xl" aria-hidden="true">
          🎥
        </span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className="h-56 w-full object-cover"
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

export default function WishlistPage() {
  const { profile, loading: authLoading } = useAuth();
  const { location } = useLocation();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!profile) {
      setLoading(false);
      return;
    }
    wishlistApi
      .list()
      .then(setItems)
      .catch((e: any) => toast.error(e.message || "Could not load your wishlist"))
      .finally(() => setLoading(false));
  }, [profile?.id, authLoading]);

  const remove = async (eventId: string) => {
    try {
      await wishlistApi.remove(eventId);
      setItems((list) => list.filter((i) => i.event_id !== eventId));
      toast.success("Removed from wishlist");
    } catch (e: any) {
      toast.error(e.message || "Could not remove");
    }
  };

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1800px] px-4 py-8 sm:px-6 lg:px-10">
      <h1 className="text-3xl font-bold text-white">❤️ My Wishlist</h1>
      <p className="mt-1 text-sm text-slate-400">Movies and events you saved to watch later.</p>

      <div className="mt-6">
        {authLoading || loading ? (
          <p className="py-16 text-center text-slate-400">Loading…</p>
        ) : !profile ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-16 text-center">
            <p className="font-semibold text-white">Log in to see your wishlist</p>
            <Link href="/auth/login" className="btn-primary mt-4 inline-block">
              Log in
            </Link>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-6 py-16 text-center">
            <p className="mb-2 text-4xl" aria-hidden="true">
              🤍
            </p>
            <p className="font-semibold text-white">Nothing saved yet</p>
            <p className="mt-1 text-sm text-slate-400">Tap the heart on any show to save it here.</p>
            <Link href="/browse" className="btn-primary mt-4 inline-block">
              Browse shows
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {items.map((it) => (
              <div
                key={it.event_id}
                className="flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900"
              >
                <WishPoster src={it.poster_url} alt={`${it.title} poster`} />
                <div className="flex flex-1 flex-col p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-lg font-bold text-white">{it.title}</h3>
                    <span className="shrink-0 rounded-md border border-slate-700 px-2 py-1 text-xs capitalize text-slate-300">
                      {it.event_type || "Show"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {[it.language, it.genre, it.duration_minutes ? `${it.duration_minutes} mins` : null]
                      .filter(Boolean)
                      .join(" • ")}
                  </p>

                  <p className="mt-3 text-sm text-slate-300">
                    {it.is_bookable ? (
                      <>
                        ◷ Next show: {fmt(it.next_show_time)}
                        <span className="text-slate-500"> · {it.shows_count} upcoming</span>
                        {location && it.latitude != null && it.longitude != null && (
                          <span className="mt-1 block text-xs font-semibold text-emerald-400">
                            📍 {it.venue_name ? `${it.venue_name} (${formatDistance(haversineKm(location.lat, location.lng, it.latitude, it.longitude), true)})` : formatDistance(haversineKm(location.lat, location.lng, it.latitude, it.longitude), true)}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-amber-400">No upcoming shows right now</span>
                    )}
                  </p>

                  <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                    {it.is_bookable ? (
                      <Link href={`/events/${it.event_id}`} className="btn-primary px-4 py-2 text-sm">
                        Book now
                      </Link>
                    ) : (
                      <span />
                    )}
                    <button
                      type="button"
                      onClick={() => remove(it.event_id)}
                      className="text-sm text-slate-400 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
