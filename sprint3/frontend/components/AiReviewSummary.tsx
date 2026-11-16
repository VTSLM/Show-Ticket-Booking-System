"use client";

import { useEffect, useState } from "react";
import { reviewsApi, AiReviewSummary } from "@/lib/reviewsApi";

/**
 * Normalizes AI-generated list fields so the UI does not crash if the backend
 * returns an array, a JSON string, or an object containing list values.
 */
function normalizeItems(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .flatMap((item) => {
        if (typeof item === "string") return [item];
        if (item === null || item === undefined) return [];
        return [String(item)];
      })
      .filter(Boolean);
  }

  if (typeof value === "string") {
    const trimmed = value.trim();

    if (!trimmed) return [];

    // Handle a JSON-encoded array returned as a string.
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map(String).filter(Boolean);
      }
    } catch {
      // Treat a normal string as one list item.
    }

    return [trimmed];
  }

  if (value && typeof value === "object") {
    const objectValue = value as Record<string, unknown>;

    // Handle common wrapped shapes such as { items: [...] } or { points: [...] }.
    for (const key of ["items", "points", "list", "values"]) {
      if (key in objectValue) {
        return normalizeItems(objectValue[key]);
      }
    }

    // If the object is a keyed collection of strings, use its values.
    return Object.values(objectValue)
      .filter((item): item is string => typeof item === "string")
      .filter(Boolean);
  }

  return [];
}

export default function AiReviewSummaryCard({ eventId }: { eventId: string }) {
  const [data, setData] = useState<AiReviewSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    reviewsApi
      .aiSummary(eventId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message || "Unable to load AI review summary");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [eventId]);

  if (loading) {
    return (
      <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-48 rounded bg-slate-800" />
          <div className="h-4 w-full rounded bg-slate-800" />
          <div className="h-4 w-5/6 rounded bg-slate-800" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <p className="text-sm font-semibold text-slate-300">🤖 AI Review Summary</p>
        <p className="mt-2 text-sm text-slate-500">{error}</p>
      </section>
    );
  }

  if (!data || data.review_count === 0) {
    return (
      <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <p className="text-sm font-semibold text-slate-300">🤖 AI Review Summary</p>
        <p className="mt-2 text-sm text-slate-500">
          There are not enough published reviews to generate an overview yet.
        </p>
      </section>
    );
  }

  const audienceLiked = normalizeItems(data.audience_liked);
  const audienceDisliked = normalizeItems(data.audience_disliked);
  const criticLiked = normalizeItems(data.critic_liked);
  const criticDisliked = normalizeItems(data.critic_disliked);

  const section = (title: string, items: string[], positive: boolean) => (
    <div>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
        {title}
      </p>
      <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
        {items.length ? (
          items.map((item, i) => (
            <li key={`${title}-${i}`} className="flex gap-2">
              <span
                className={positive ? "text-emerald-400" : "text-rose-400"}
              >
                {positive ? "✓" : "•"}
              </span>
              <span>{item}</span>
            </li>
          ))
        ) : (
          <li className="text-slate-500">No recurring point identified.</li>
        )}
      </ul>
    </div>
  );

  return (
    <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">
            🤖 AI Review Summary
          </p>
          <h2 className="mt-1 text-xl font-bold text-white">
            What audiences and critics think
          </h2>
        </div>
        <div className="flex gap-2 text-center">
          <div className="rounded-xl bg-slate-800/70 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Audience
            </p>
            <p className="text-lg font-bold text-white">
              {data.audience_rating.toFixed(1)}
              <span className="text-xs text-slate-500">/10</span>
            </p>
          </div>
          <div className="rounded-xl bg-slate-800/70 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Critics
            </p>
            <p className="text-lg font-bold text-white">
              {data.critic_rating.toFixed(1)}
              <span className="text-xs text-slate-500">/10</span>
            </p>
          </div>
          <div className="rounded-xl bg-blue-500/10 px-3 py-2 ring-1 ring-blue-500/20">
            <p className="text-[10px] uppercase tracking-wider text-blue-300">
              Overall
            </p>
            <p className="text-lg font-bold text-blue-300">
              {data.overall_rating.toFixed(1)}
              <span className="text-xs">/10</span>
            </p>
          </div>
        </div>
      </div>

      <p className="mt-5 text-sm leading-6 text-slate-300">
        {data.overall_summary}
      </p>

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <div className="rounded-xl bg-slate-950/40 p-4">
          <p className="text-sm font-semibold text-white">Audience</p>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {data.audience_summary}
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {section("Liked", audienceLiked, true)}
            {section("Criticisms", audienceDisliked, false)}
          </div>
        </div>

        <div className="rounded-xl bg-slate-950/40 p-4">
          <p className="text-sm font-semibold text-white">Critics</p>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {data.critic_summary}
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {section("Liked", criticLiked, true)}
            {section("Criticisms", criticDisliked, false)}
          </div>
        </div>
      </div>

      <p className="mt-4 text-[11px] text-slate-600">
        Based on {data.review_count} published review
        {data.review_count === 1 ? "" : "s"}. AI-generated overview; ratings are
        calculated from the stored review ratings.
      </p>
    </section>
  );
}
