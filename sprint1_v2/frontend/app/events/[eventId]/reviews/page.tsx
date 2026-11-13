"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  reviewsApi,
  Audience,
  EventReviews,
  MyReview,
  Review,
  SortBy,
} from "@/lib/reviewsApi";

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { dateStyle: "medium" });

function ScoreCard({
  label,
  score,
  fresh,
  total,
}: {
  label: string;
  score: number;
  fresh: number;
  total: number;
}) {
  return (
    <div className="card text-center">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      {total === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No reviews yet</p>
      ) : (
        <>
          <p className="mt-2 text-4xl font-bold text-blue-400">
            {score.toFixed(1)}
            <span className="text-lg text-slate-500">/10</span>
          </p>
          <p className="mt-1 text-sm text-slate-300">{fresh}% positive</p>
          <p className="text-xs text-slate-500">
            {total} {total === 1 ? "review" : "reviews"}
          </p>
        </>
      )}
    </div>
  );
}

function ReviewCard({
  review,
  token,
  onChange,
  canManage,
  onEdit,
  onDelete,
}: {
  review: Review;
  token: string | null;
  onChange: (r: Review) => void;
  canManage: boolean;
  onEdit: (r: Review) => void;
  onDelete: (r: Review) => void;
}) {
  const [revealed, setRevealed] = useState(!review.is_spoiler);
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const isCritic = review.author.role === "critic" || review.author.is_verified;

  const upvote = async () => {
    if (!token) return toast.error("Log in to upvote");
    try {
      const res = await reviewsApi.toggleUpvote(token, review.id);
      onChange({ ...review, has_upvoted: res.upvoted, upvotes_count: res.upvotes_count });
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const postComment = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!token) return toast.error("Log in to comment");
    if (!comment.trim()) return;
    setBusy(true);
    try {
      const c = await reviewsApi.comment(token, review.id, comment.trim());
      onChange({
        ...review,
        comments: [...review.comments, c],
        comments_count: review.comments_count + 1,
      });
      setComment("");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  const comments = [...review.comments].sort(
    (a, b) => Number(b.is_pinned) - Number(a.is_pinned)
  );

  return (
    <article className="card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-semibold text-white">
            {review.author.name}
            {isCritic && (
              <span className="ml-2 rounded-md bg-blue-500/20 px-2 py-0.5 text-xs text-blue-300">
                {review.author.publication ? `Critic · ${review.author.publication}` : "Critic"}
              </span>
            )}
          </p>
          <p className="text-xs text-slate-500">
            {fmtDate(review.published_at)}
            {review.version > 1 && " · edited"}
          </p>
        </div>
        <div className="shrink-0 rounded-xl border border-slate-700 px-3 py-1 text-lg font-bold text-blue-400">
          {review.rating.toFixed(1)}
        </div>
      </div>

      <h3 className="mt-3 text-lg font-bold text-white">{review.headline}</h3>

      {revealed ? (
        <p className="mt-2 whitespace-pre-line text-sm text-slate-300">{review.content}</p>
      ) : (
        <button
          onClick={() => setRevealed(true)}
          className="mt-2 w-full rounded-lg border border-amber-500/40 bg-amber-500/10 py-4 text-sm text-amber-300"
        >
          ⚠ Contains spoilers — click to reveal
        </button>
      )}

      {revealed && review.sections && Object.keys(review.sections).length > 0 && (
        <div className="mt-3 space-y-2">
          {Object.entries(review.sections).map(([k, v]) => (
            <div key={k}>
              <p className="text-xs font-semibold uppercase text-slate-400">{k}</p>
              <p className="text-sm text-slate-300">{v}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center gap-4 border-t border-slate-800 pt-3 text-sm">
        <button
          onClick={upvote}
          className={review.has_upvoted ? "font-semibold text-blue-400" : "text-slate-400 hover:text-white"}
        >
          👍 Helpful ({review.upvotes_count})
        </button>
        <button
          onClick={() => setShowComments((s) => !s)}
          className="text-slate-400 hover:text-white"
        >
          💬 Comments ({review.comments_count})
        </button>
        {canManage && (
          <span className="ml-auto flex gap-4">
            <button onClick={() => onEdit(review)} className="text-slate-400 hover:text-white">
              ✏️ Edit
            </button>
            <button onClick={() => onDelete(review)} className="text-red-400 hover:text-red-300">
              🗑 Delete
            </button>
          </span>
        )}
      </div>

      {showComments && (
        <div className="mt-3 space-y-3">
          {comments.map((c) => (
            <div key={c.id} className="rounded-lg bg-slate-900/70 p-3 text-sm">
              <p className="font-medium text-slate-200">
                {c.author_name}
                {c.is_critic && <span className="ml-2 text-xs text-blue-300">Critic</span>}
                {c.is_pinned && <span className="ml-2 text-xs text-amber-300">📌 Pinned</span>}
              </p>
              <p className="mt-1 text-slate-300">{c.content}</p>
            </div>
          ))}
          <form onSubmit={postComment} className="flex gap-2">
            <input
              className="input flex-1"
              placeholder={token ? "Add a comment…" : "Log in to comment"}
              value={comment}
              maxLength={1000}
              onChange={(e) => setComment(e.target.value)}
              disabled={!token}
            />
            <button className="btn-secondary" disabled={busy || !token}>
              Post
            </button>
          </form>
        </div>
      )}
    </article>
  );
}

export default function EventReviewsPage() {
  // Read the id from the URL no matter what the dynamic folder is named
  // ([eventId], [eventid], [id] ...).
  const params = useParams();
  const eventId = String(Object.values(params ?? {})[0] ?? "");
  const { user, profile, isAdmin, loading: authLoading } = useAuth();

  const [data, setData] = useState<EventReviews | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [audience, setAudience] = useState<Audience>("all");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [token, setToken] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ rating: 8, headline: "", content: "", is_spoiler: false });
  const [submitting, setSubmitting] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [mine, setMine] = useState<MyReview | null>(null);

  // Resolve the Firebase token once auth has settled
  useEffect(() => {
    if (authLoading) return;
    if (!user) return setToken(null);
    user.getIdToken().then(setToken).catch(() => setToken(null));
  }, [user, authLoading]);

  const load = useCallback(async () => {
    if (authLoading) return;
    if (!eventId || eventId === "undefined") {
      setError("Event id missing in URL");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await reviewsApi.forEvent(eventId, { audience, sortBy, token }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [eventId, audience, sortBy, token, authLoading]);

  useEffect(() => {
    load();
  }, [load]);

  // The logged-in user's own review for this event (one review per user)
  const loadMine = useCallback(async () => {
    if (!token || !eventId) return setMine(null);
    try {
      setMine((await reviewsApi.mine(token, eventId)).review);
    } catch {
      setMine(null);
    }
  }, [token, eventId]);

  useEffect(() => {
    loadMine();
  }, [loadMine]);

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!token) return toast.error("Log in to write a review");
    setSubmitting(true);
    try {
      if (editingId) {
        await reviewsApi.update(token, editingId, form);
        toast.success("Review updated");
      } else {
        await reviewsApi.submit(token, { event_id: eventId, ...form });
        toast.success("Review submitted");
      }
      setEditingId(null);
      setShowForm(false);
      setForm({ rating: 8, headline: "", content: "", is_spoiler: false });
      load();
      loadMine();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const emptyForm = { rating: 8, headline: "", content: "", is_spoiler: false };

  const toggleForm = () => {
    if (showForm) {
      setShowForm(false);
      setEditingId(null);
    } else if (mine) {
      // already reviewed -> open the form in edit mode
      setEditingId(mine.id);
      setForm({
        rating: mine.rating,
        headline: mine.headline,
        content: mine.content,
        is_spoiler: mine.is_spoiler,
      });
      setShowForm(true);
    } else {
      setEditingId(null);
      setForm(emptyForm);
      setShowForm(true);
    }
  };

  const startEdit = (r: Review) => {
    setEditingId(r.id);
    setForm({
      rating: r.rating,
      headline: r.headline,
      content: r.content,
      is_spoiler: r.is_spoiler,
    });
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const removeReview = async (r: Review) => {
    if (!token) return toast.error("Log in first");
    if (!window.confirm("Delete this review? This cannot be undone.")) return;
    try {
      await reviewsApi.remove(token, r.id);
      toast.success("Review deleted");
      load();
      loadMine();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const updateReview = (r: Review) =>
    setData((d) => (d ? { ...d, reviews: d.reviews.map((x) => (x.id === r.id ? r : x)) } : d));

  const a = data?.aggregates;

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8 sm:px-6">
      <Link href="/browse" className="text-sm text-slate-400 hover:text-white">
        ← Back to shows
      </Link>
      <h1 className="mt-3 text-3xl font-bold text-white">Reviews &amp; Ratings</h1>

      {a && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <ScoreCard
            label="Critics"
            score={a.average_critic_score}
            fresh={a.critic_fresh_percentage}
            total={a.total_critic_reviews}
          />
          <ScoreCard
            label="Audience"
            score={a.average_user_score}
            fresh={a.user_fresh_percentage}
            total={a.total_user_reviews}
          />
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {(["all", "critics", "audience"] as Audience[]).map((t) => (
            <button
              key={t}
              onClick={() => setAudience(t)}
              className={`rounded-full border px-4 py-1.5 text-sm capitalize ${
                audience === t
                  ? "border-blue-500 bg-blue-500/20 text-blue-300"
                  : "border-slate-700 text-slate-400 hover:text-white"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <select
          className="input !w-auto"
          aria-label="Sort reviews"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
        >
          <option value="newest">Newest</option>
          <option value="highest">Highest rated</option>
          <option value="lowest">Lowest rated</option>
          <option value="helpful">Most helpful</option>
        </select>
      </div>

      <div className="mt-6">
        {user ? (
          <button className="btn-primary" onClick={toggleForm}>
            {showForm ? "Cancel" : mine ? "Edit your review" : "Write a review"}
          </button>
        ) : (
          <Link href="/auth/login" className="btn-secondary">
            Log in to write a review
          </Link>
        )}
      </div>

      {showForm && (
        <form onSubmit={submit} className="card mt-4 space-y-3">
          <p className="font-semibold text-white">
            {editingId ? "Edit your review" : "Write a review"}
          </p>
          <div>
            <label className="text-sm text-slate-300">Rating: {form.rating.toFixed(1)} / 10</label>
            <input
              type="range"
              min={1}
              max={10}
              step={0.5}
              value={form.rating}
              onChange={(e) => setForm({ ...form, rating: Number(e.target.value) })}
              className="w-full"
            />
          </div>
          <input
            className="input"
            placeholder="Headline (3–255 chars)"
            value={form.headline}
            minLength={3}
            maxLength={255}
            required
            onChange={(e) => setForm({ ...form, headline: e.target.value })}
          />
          <textarea
            className="input min-h-[120px]"
            placeholder="Your review (min 10 chars)"
            value={form.content}
            minLength={10}
            required
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={form.is_spoiler}
              onChange={(e) => setForm({ ...form, is_spoiler: e.target.checked })}
            />
            Contains spoilers
          </label>
          <button className="btn-primary" disabled={submitting}>
            {submitting ? "Saving…" : editingId ? "Save changes" : "Submit review"}
          </button>
        </form>
      )}

      <div className="mt-6 space-y-4">
        {loading ? (
          <div className="py-16 text-center text-slate-400">Loading reviews…</div>
        ) : error ? (
          <div className="py-16 text-center text-red-400">{error}</div>
        ) : data && data.reviews.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            No reviews yet — be the first to write one.
          </div>
        ) : (
          data?.reviews.map((r) => (
            <ReviewCard
              key={r.id}
              review={r}
              token={token}
              onChange={updateReview}
              canManage={Boolean(isAdmin) || (!!profile?.id && String(profile.id) === String(r.user_id))}
              onEdit={startEdit}
              onDelete={removeReview}
            />
          ))
        )}
      </div>
    </div>
  );
}
