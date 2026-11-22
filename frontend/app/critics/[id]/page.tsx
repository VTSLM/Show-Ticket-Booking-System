"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CriticProfile, reviewsApi } from "@/lib/reviewsApi";

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { dateStyle: "medium" });

export default function CriticProfilePage() {
  const params = useParams();
  const criticId = params.id as string;

  const [profile, setProfile] = useState<CriticProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!criticId) return;
    setLoading(true);
    setError(null);
    reviewsApi
      .criticProfile(criticId)
      .then((data) => setProfile(data))
      .catch((err) => setError(err.message || "Critic profile not found"))
      .finally(() => setLoading(false));
  }, [criticId]);

  if (loading) {
    return (
      <main className="container-page py-12 text-center">
        <p className="text-slate-400">Loading critic profile…</p>
      </main>
    );
  }

  if (error || !profile) {
    return (
      <main className="container-page py-12 text-center">
        <h1 className="text-2xl font-bold text-white">Critic Profile Not Found</h1>
        <p className="mt-2 text-slate-400">{error || "This critic profile does not exist or has been removed."}</p>
        <Link href="/browse" className="btn-primary mt-6 inline-block">
          Browse Events
        </Link>
      </main>
    );
  }

  return (
    <main className="container-page space-y-8 py-8">
      {/* ── Critic Header ── */}
      <div className="card flex flex-col items-center gap-6 sm:flex-row sm:items-start">
        {profile.avatar_url ? (
          <img
            src={profile.avatar_url}
            alt={profile.name}
            className="h-28 w-28 rounded-full border-2 border-blue-500/40 object-cover shadow-lg"
          />
        ) : (
          <div className="flex h-28 w-28 items-center justify-center rounded-full border-2 border-blue-500/40 bg-blue-950/60 text-4xl font-bold text-blue-300">
            {profile.name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="flex-1 text-center sm:text-left">
          <div className="flex flex-wrap items-center justify-center gap-3 sm:justify-start">
            <h1 className="text-3xl font-extrabold text-white">{profile.name}</h1>
            <span className="rounded-full bg-blue-500/20 px-3 py-1 text-xs font-semibold text-blue-300 border border-blue-500/30">
              Verified Film Critic
            </span>
          </div>
          {profile.publication && (
            <p className="mt-1 text-sm font-medium text-blue-400">
              Publication: <span className="text-slate-200">{profile.publication}</span>
            </p>
          )}
          {profile.bio && (
            <p className="mt-3 text-sm text-slate-300 whitespace-pre-line max-w-2xl">{profile.bio}</p>
          )}
        </div>
      </div>

      {/* ── Critic Statistics ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Total Reviews</p>
          <p className="mt-2 text-3xl font-bold text-white">{profile.total_reviews}</p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Average Rating</p>
          <p className="mt-2 text-3xl font-bold text-blue-400">
            {profile.average_rating.toFixed(1)}
            <span className="text-base text-slate-500">/10</span>
          </p>
        </div>
        <div className="card text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Fresh Rate</p>
          <p className="mt-2 text-3xl font-bold text-emerald-400">{profile.fresh_percentage}%</p>
          <p className="text-xs text-slate-500">rated 6.0 or higher</p>
        </div>
      </div>

      {/* ── Rating Distribution ── */}
      {profile.total_reviews > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Rating History & Distribution</h2>
          <div className="mt-4 grid grid-cols-10 gap-2 items-end h-28 pt-4">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((score) => {
              const count = profile.rating_history[String(score)] || 0;
              const pct = profile.total_reviews > 0 ? (count / profile.total_reviews) * 100 : 0;
              return (
                <div key={score} className="flex flex-col items-center gap-1 h-full justify-end">
                  <div
                    className="w-full rounded-t bg-blue-500/60 transition-all hover:bg-blue-400"
                    style={{ height: `${Math.max(pct, count > 0 ? 10 : 2)}%` }}
                    title={`${score}/10: ${count} review(s)`}
                  />
                  <span className="text-[10px] text-slate-400">{score}★</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Published Reviews List ── */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white">Published Reviews ({profile.reviews.length})</h2>
        {profile.reviews.length === 0 ? (
          <p className="card text-center text-slate-500">No published reviews yet.</p>
        ) : (
          profile.reviews.map((rev) => (
            <article key={rev.id} className="card space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <Link
                    href={`/events/${rev.event_id}/reviews`}
                    className="text-lg font-bold text-white hover:text-blue-400 hover:underline"
                  >
                    {rev.event_title}
                  </Link>
                  {rev.event_genre && (
                    <span className="ml-2 text-xs text-slate-400">({rev.event_genre})</span>
                  )}
                  <p className="text-xs text-slate-500">{fmtDate(rev.published_at)}</p>
                </div>
                <div className="shrink-0 rounded-xl border border-blue-500/40 bg-blue-950/40 px-3 py-1 text-lg font-bold text-blue-400">
                  {rev.rating.toFixed(1)}/10
                </div>
              </div>

              <h3 className="font-semibold text-slate-200">{rev.headline}</h3>
              <p className="text-sm text-slate-300 whitespace-pre-line">{rev.content}</p>

              {/* Review Sections */}
              {rev.sections && Object.keys(rev.sections).length > 0 && (
                <div className="mt-3 space-y-2 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  {Object.entries(rev.sections).map(([sec, txt]) => (
                    <div key={sec}>
                      <span className="text-xs font-semibold uppercase text-blue-400">{sec}: </span>
                      <span className="text-xs text-slate-300">{txt}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Media Attachment */}
              {rev.media_url && (
                <div className="mt-3 pt-2">
                  {rev.media_url.match(/\.(jpeg|jpg|gif|png|webp)($|\?)/i) ? (
                    <img
                      src={rev.media_url}
                      alt="Critic attachment"
                      className="max-h-60 rounded-lg object-cover"
                    />
                  ) : rev.media_url.match(/\.(mp4|webm)($|\?)/i) ? (
                    <video src={rev.media_url} controls className="max-h-60 rounded-lg" />
                  ) : (
                    <a
                      href={rev.media_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:underline"
                    >
                      🎬 Watch Attached Trailer / Media Clip
                    </a>
                  )}
                </div>
              )}

              <div className="pt-2 text-xs text-slate-500">
                👍 {rev.upvotes_count} found this helpful
              </div>
            </article>
          ))
        )}
      </div>
    </main>
  );
}
