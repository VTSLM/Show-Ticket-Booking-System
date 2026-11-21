"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import AiReviewSummaryCard from "@/components/AiReviewSummary";
import {
  reviewsApi,
  Audience,
  EventReviews,
  MyReview,
  Review,
  ReviewComment,
  ReportReason,
  SortBy,
} from "@/lib/reviewsApi";

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { dateStyle: "medium" });

const fmtDateTime = (d: string) =>
  new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

// <input type="datetime-local"> works with local "YYYY-MM-DDTHH:mm" strings
const toLocalInput = (d: Date) => {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const MIN_LEAD_MS = 2 * 60 * 1000; // pick a time at least 2 minutes ahead (server needs 1)
const minScheduleInput = () => toLocalInput(new Date(Date.now() + MIN_LEAD_MS));
const maxScheduleInput = () => toLocalInput(new Date(Date.now() + 364 * 24 * 60 * 60 * 1000));

// "TF Verified" = reviews by people who booked a ticket for this event on TicketFlow
type ReviewTab = Audience | "verified";

// "Watched on 14 Nov, PVR Ahmedabad" — from the show the reviewer booked
const watchedLine = (r: Review) => {
  if (!r.watched_at) return null;
  const day = new Date(r.watched_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  const place = [r.watched_venue, r.watched_city].filter(Boolean).join(" ");
  return place ? `Watched on ${day}, ${place}` : `Watched on ${day}`;
};

const EMPTY_FORM = {
  rating: 8,
  headline: "",
  content: "",
  is_spoiler: false,
  media_url: "",
  sections: {} as Record<string, string>,
};

const CRITIC_SECTION_OPTIONS = [
  "Story",
  "Direction",
  "Performances",
  "Cinematography",
  "Music",
  "Verdict",
];

const countWords = (text: string, secs?: Record<string, string>) => {
  let count = text.trim() ? text.trim().split(/\s+/).length : 0;
  if (secs) {
    for (const v of Object.values(secs)) {
      if (v?.trim()) count += v.trim().split(/\s+/).length;
    }
  }
  return count;
};

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

const REPORT_REASONS: [ReportReason, string][] = [
  ["spam", "Spam or advertising"],
  ["abusive", "Abusive or offensive"],
  ["spoiler", "Spoiler not marked"],
  ["off_topic", "Not about this event"],
  ["other", "Something else"],
];

function ReviewCard({
  review,
  token,
  onChange,
  canManage,
  isMine,
  hideSpoilers,
  onEdit,
  onDelete,
}: {
  review: Review;
  token: string | null;
  onChange: (r: Review) => void;
  canManage: boolean;
  isMine: boolean;
  hideSpoilers: boolean;
  onEdit: (r: Review) => void;
  onDelete: (r: Review) => void;
}) {
  const router = useRouter();
  const [clicked, setClicked] = useState(false);
  // Spoiler reviews stay covered while "Hide spoilers" is on, unless this card was clicked open
  const revealed = !review.is_spoiler || !hideSpoilers || clicked;
  const setRevealed = (v: boolean) => setClicked(v);
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [replyTo, setReplyTo] = useState<string | null>(null); // id of the thread being replied to
  const [replyText, setReplyText] = useState("");
  const [showReport, setShowReport] = useState(false);
  const [reportReason, setReportReason] = useState<ReportReason>("spam");
  const [reportDetails, setReportDetails] = useState("");

  const isCritic = review.author.role === "critic" || review.author.is_verified;

  const upvote = async () => {
    if (!token) {
      toast.error("Log in to mark reviews helpful");
      router.push("/auth/login");
      return;
    }
    try {
      const res = await reviewsApi.toggleUpvote(token, review.id);
      onChange({ ...review, has_upvoted: res.upvoted, upvotes_count: res.upvotes_count });
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const sendComment = async (text: string, parentId?: string): Promise<boolean> => {
    if (!token) {
      toast.error("Log in to comment");
      return false;
    }
    if (!text.trim()) return false;
    setBusy(true);
    try {
      const c = await reviewsApi.comment(token, review.id, text.trim(), parentId);
      onChange({
        ...review,
        comments: [...review.comments, c],
        comments_count: review.comments_count + 1,
      });
      return true;
    } catch (e: any) {
      toast.error(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const submitReport = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!token) return toast.error("Log in to report a review");
    setBusy(true);
    try {
      await reviewsApi.report(token, review.id, reportReason, reportDetails);
      toast.success("Thanks, the review was reported to the managers");
      onChange({ ...review, has_reported: true });
      setShowReport(false);
      setReportDetails("");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  const postComment = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (await sendComment(comment)) setComment("");
  };

  const postReply = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!replyTo) return;
    if (await sendComment(replyText, replyTo)) {
      setReplyText("");
      setReplyTo(null);
    }
  };

  // Replying to a reply keeps the thread one level deep (the server does the same)
  const startReply = (thread: ReviewComment, target: ReviewComment) => {
    setReplyTo(thread.id);
    setReplyText(target.id === thread.id ? "" : `@${target.author_name} `);
  };

  // Top-level comments (pinned first) and their replies (oldest first)
  const topLevel = review.comments
    .filter((c) => !c.parent_comment_id)
    .sort((x, y) => Number(y.is_pinned) - Number(x.is_pinned));
  const repliesOf = (id: string) => review.comments.filter((c) => c.parent_comment_id === id);

  const renderComment = (c: ReviewComment, thread: ReviewComment, isReply: boolean) => (
    <div
      key={c.id}
      className={`rounded-lg p-3 text-sm ${isReply ? "bg-slate-900/40" : "bg-slate-900/70"}`}
    >
      <p className="font-medium text-slate-200">
        {c.author_name}
        {c.is_review_author && (
          <span className="ml-2 rounded bg-emerald-500/20 px-1.5 py-0.5 text-xs text-emerald-300">
            Author
          </span>
        )}
        {c.is_critic && <span className="ml-2 text-xs text-blue-300">Critic</span>}
        {c.is_pinned && <span className="ml-2 text-xs text-amber-300">📌 Pinned</span>}
        <span className="ml-2 text-xs font-normal text-slate-500">{fmtDate(c.created_at)}</span>
      </p>
      <p className="mt-1 whitespace-pre-line text-slate-300">{c.content}</p>
      {token && (
        <button
          onClick={() => startReply(thread, c)}
          className="mt-1 text-xs text-slate-400 hover:text-white"
        >
          ↩ Reply
        </button>
      )}
    </div>
  );

  return (
    <article className="card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-semibold text-white">
            {isCritic ? (
              <Link href={`/critics/${review.user_id}`} className="hover:text-blue-400 hover:underline">
                {review.author.name}
              </Link>
            ) : (
              review.author.name
            )}
            {review.is_verified_attendee && (
              <span
                className="ml-2 rounded-md bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300"
                title="This reviewer booked a ticket for this event on TicketFlow"
              >
                ✓ Verified attendee
              </span>
            )}
            {isCritic && (
              <Link
                href={`/critics/${review.user_id}`}
                className="ml-2 rounded-md bg-blue-500/20 px-2 py-0.5 text-xs text-blue-300 hover:bg-blue-500/30 transition-colors"
              >
                {review.author.publication ? `Critic · ${review.author.publication}` : "Critic"}
              </Link>
            )}
          </p>
          <p className="text-xs text-slate-500">
            {fmtDate(review.published_at)}
            {review.version > 1 && " · edited"}
            {review.is_verified_attendee && " · Booked on TicketFlow"}
          </p>
          {watchedLine(review) && (
            <p className="text-xs text-emerald-300/80">🎟 {watchedLine(review)}</p>
          )}
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

      {revealed && review.media_url && (
        <div className="mt-3 pt-1">
          {review.media_url.match(/\.(jpeg|jpg|gif|png|webp)($|\?)/i) ? (
            <img
              src={review.media_url}
              alt="Review media attachment"
              className="max-h-72 rounded-lg object-cover"
            />
          ) : review.media_url.match(/\.(mp4|webm)($|\?)/i) ? (
            <video src={review.media_url} controls className="max-h-72 rounded-lg" />
          ) : (
            <a
              href={review.media_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/30 bg-blue-950/40 px-3 py-1.5 text-xs font-medium text-blue-300 hover:bg-blue-900/40 hover:underline"
            >
              🎬 Watch Attached Trailer / Media Clip ↗
            </a>
          )}
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
        {!isMine && (
          <button
            onClick={() => {
              if (!token) return toast.error("Log in to report a review");
              if (review.has_reported) return;
              setShowReport((v) => !v);
            }}
            disabled={review.has_reported}
            className="text-slate-500 hover:text-red-300 disabled:cursor-default disabled:hover:text-slate-500"
          >
            {review.has_reported ? "🚩 Reported" : "🚩 Report"}
          </button>
        )}
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

      {showReport && !review.has_reported && (
        <form
          onSubmit={submitReport}
          className="mt-3 space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4"
        >
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
            Report this review
          </p>
          <div className="space-y-2">
            {REPORT_REASONS.map(([value, label]) => (
              <label key={value} className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name={`report-${review.id}`}
                  checked={reportReason === value}
                  onChange={() => setReportReason(value)}
                />
                {label}
              </label>
            ))}
          </div>
          <textarea
            className="input min-h-[70px] text-sm"
            maxLength={500}
            placeholder="Add details (optional)"
            value={reportDetails}
            onChange={(e) => setReportDetails(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Sending…" : "Submit report"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowReport(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {showComments && (
        <div className="mt-3 space-y-3">
          {topLevel.map((c) => {
            const replies = repliesOf(c.id);
            return (
              <div key={c.id} className="space-y-2">
                {renderComment(c, c, false)}
                {replies.length > 0 && (
                  <div className="ml-6 space-y-2 border-l border-slate-800 pl-3">
                    {replies.map((r) => renderComment(r, c, true))}
                  </div>
                )}
                {replyTo === c.id && (
                  <form onSubmit={postReply} className="ml-6 flex flex-wrap gap-2">
                    <input
                      className="input min-w-0 flex-1"
                      autoFocus
                      placeholder="Write a reply…"
                      value={replyText}
                      maxLength={1000}
                      onChange={(e) => setReplyText(e.target.value)}
                    />
                    <button className="btn-secondary" disabled={busy}>
                      Reply
                    </button>
                    <button
                      type="button"
                      className="text-xs text-slate-400 hover:text-white"
                      onClick={() => {
                        setReplyTo(null);
                        setReplyText("");
                      }}
                    >
                      Cancel
                    </button>
                  </form>
                )}
              </div>
            );
          })}
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
  const { user, profile, isAdmin, isCritic, loading: authLoading } = useAuth();

  const [data, setData] = useState<EventReviews | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [audience, setAudience] = useState<ReviewTab>("all");
  const [sortBy, setSortBy] = useState<SortBy>("newest");
  const [hideSpoilers, setHideSpoilers] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [publishMode, setPublishMode] = useState<"draft" | "now" | "later">("now");
  const [scheduleAt, setScheduleAt] = useState(""); // local "YYYY-MM-DDTHH:mm"
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
      // "TF Verified" loads everyone and keeps only the verified attendees
      const res = await reviewsApi.forEvent(eventId, {
        audience: audience === "verified" ? "all" : audience,
        sortBy,
        token,
      });
      setData(
        audience === "verified"
          ? { ...res, reviews: res.reviews.filter((r) => r.is_verified_attendee) }
          : res
      );
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

  // While my review is scheduled, check back so it appears when its time arrives
  useEffect(() => {
    if (!mine?.is_scheduled || !mine.scheduled_for) return undefined;
    const at = new Date(mine.scheduled_for).getTime();
    const id = setInterval(() => {
      if (Date.now() >= at) {
        load();
        loadMine();
      }
    }, 30000);
    return () => clearInterval(id);
  }, [mine, load, loadMine]);

  // What am I editing?  a draft, a scheduled review, or a published one
  const editingDraft = Boolean(mine?.is_draft && editingId === mine.id);
  const editingScheduled = Boolean(mine?.is_scheduled && editingId === mine.id);
  // Publish options (now / schedule / draft): new reviews, drafts and scheduled reviews
  const showPublishOptions = !editingId || editingDraft || editingScheduled;

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setPublishMode("now");
    setScheduleAt("");
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!token) return toast.error("Log in to write a review");

    // How should it go live?  now | later | draft
    let scheduledIso: string | null = null;
    if (showPublishOptions && publishMode === "later") {
      const t = new Date(scheduleAt).getTime();
      if (!scheduleAt || Number.isNaN(t)) return toast.error("Pick a date and time to publish");
      if (t < Date.now() + MIN_LEAD_MS) return toast.error("Pick a time at least 2 minutes from now");
      scheduledIso = new Date(t).toISOString();
    }

    if (isCritic) {
      const words = countWords(form.content, form.sections);
      if (words < 10) return toast.error(`Critic review must be at least 10 words (currently ${words} words)`);
      if (words > 1000) return toast.error(`Critic review cannot exceed 1000 words (currently ${words} words)`);
    }

    const cleanedSections = isCritic && Object.keys(form.sections).length > 0 ? form.sections : undefined;
    const cleanedMedia = isCritic && form.media_url?.trim() ? form.media_url.trim() : undefined;

    setSubmitting(true);
    try {
      if (editingId) {
        const updatePayload = {
          ...form,
          sections: cleanedSections,
          media_url: cleanedMedia,
        };
        if (showPublishOptions) {
          // editing a draft or a scheduled review
          if (publishMode === "now") {
            await reviewsApi.update(token, editingId, { ...updatePayload, publish_now: true });
            toast.success("Review published");
          } else if (publishMode === "later" && scheduledIso) {
            await reviewsApi.update(token, editingId, { ...updatePayload, scheduled_for: scheduledIso });
            toast.success(`Review scheduled for ${fmtDateTime(scheduledIso)}`);
          } else {
            await reviewsApi.update(token, editingId, { ...updatePayload, is_draft: true });
            toast.success("Draft saved");
          }
        } else {
          await reviewsApi.update(token, editingId, updatePayload);
          toast.success("Review updated");
        }
      } else {
        const extra =
          publishMode === "draft"
            ? { is_draft: true }
            : scheduledIso
              ? { scheduled_for: scheduledIso }
              : {};
        await reviewsApi.submit(token, {
          event_id: eventId,
          ...form,
          sections: cleanedSections,
          media_url: cleanedMedia,
          ...extra,
        });
        toast.success(
          publishMode === "draft"
            ? "Draft saved"
            : scheduledIso
              ? `Review scheduled for ${fmtDateTime(scheduledIso)}`
              : "Review submitted"
        );
      }
      closeForm();
      load();
      loadMine();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Open the form on my own review (also used by the "Scheduled" banner)
  const openEditMine = () => {
    if (!mine) return;
    setEditingId(mine.id);
    setForm({
      rating: mine.rating,
      headline: mine.headline,
      content: mine.content,
      is_spoiler: mine.is_spoiler,
      media_url: mine.media_url || "",
      sections: mine.sections || {},
    });
    if (mine.is_draft) {
      setPublishMode("draft");
      setScheduleAt("");
    } else if (mine.is_scheduled && mine.scheduled_for) {
      setPublishMode("later");
      setScheduleAt(toLocalInput(new Date(mine.scheduled_for)));
    } else {
      setPublishMode("now");
      setScheduleAt("");
    }
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const toggleForm = () => {
    if (showForm) {
      closeForm();
    } else if (mine) {
      // already reviewed -> open the form in edit mode
      openEditMine();
    } else {
      setEditingId(null);
      setForm(EMPTY_FORM);
      setPublishMode("now");
      setScheduleAt("");
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
      media_url: r.media_url || "",
      sections: r.sections || {},
    });
    setPublishMode("now");
    setScheduleAt("");
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const publishNow = async () => {
    if (!token || !mine) return;
    try {
      await reviewsApi.update(token, mine.id, { publish_now: true });
      toast.success("Review published");
      load();
      loadMine();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const removeReview = async (r: { id: string }) => {
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

      <AiReviewSummaryCard eventId={eventId} />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {(["all", "critics", "audience", "verified"] as ReviewTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setAudience(t)}
              className={`rounded-full border px-4 py-1.5 text-sm ${
                t === "verified" ? "italic" : "capitalize"
              } ${
                audience === t
                  ? t === "verified"
                    ? "border-emerald-500 bg-emerald-500/20 text-emerald-300"
                    : "border-blue-500 bg-blue-500/20 text-blue-300"
                  : "border-slate-700 text-slate-400 hover:text-white"
              }`}
              title={
                t === "verified"
                  ? "Reviews from people who booked this event on TicketFlow"
                  : undefined
              }
            >
              {t === "verified" ? "TF Verified" : t}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-slate-300">
            <button
              type="button"
              role="switch"
              aria-checked={hideSpoilers}
              aria-label="Hide spoilers"
              onClick={() => setHideSpoilers((v) => !v)}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                hideSpoilers ? "bg-blue-500" : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                  hideSpoilers ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
            Hide spoilers
          </label>
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
      </div>

      <div className="mt-6">
        {user ? (
          <button className="btn-primary" onClick={toggleForm}>
            {showForm ? "Cancel" : mine?.is_draft ? "Continue your draft" : mine ? "Edit your review" : "Write a review"}
          </button>
        ) : (
          <Link href="/auth/login" className="btn-secondary">
            Log in to write a review
          </Link>
        )}
      </div>

      {mine?.is_draft && !showForm && (
        <div className="card mt-4 border border-slate-600 bg-slate-800/40">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-300">
            📝 Draft — only you can see this
          </p>
          <p className="mt-3 font-semibold text-white">{mine.headline}</p>
          <p className="mt-1 whitespace-pre-line text-sm text-slate-400">
            {mine.content.length > 200 ? `${mine.content.slice(0, 200)}…` : mine.content}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            <button className="btn-primary" onClick={publishNow}>
              Publish now
            </button>
            <button className="btn-secondary" onClick={openEditMine}>
              Continue editing
            </button>
            <button
              className="text-red-400 hover:text-red-300"
              onClick={() => removeReview(mine)}
            >
              🗑 Delete
            </button>
          </div>
        </div>
      )}

      {mine?.is_scheduled && mine.scheduled_for && !showForm && (
        <div className="card mt-4 border border-amber-500/40 bg-amber-500/5">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-300">
            ⏰ Scheduled — only you can see this
          </p>
          <p className="mt-1 text-sm text-slate-300">
            Goes live on{" "}
            <span className="font-semibold text-white">{fmtDateTime(mine.scheduled_for)}</span>
          </p>
          <p className="mt-3 font-semibold text-white">{mine.headline}</p>
          <p className="mt-1 whitespace-pre-line text-sm text-slate-400">
            {mine.content.length > 200 ? `${mine.content.slice(0, 200)}…` : mine.content}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            <button className="btn-primary" onClick={publishNow}>
              Publish now
            </button>
            <button className="btn-secondary" onClick={openEditMine}>
              Edit / change time
            </button>
            <button
              className="text-red-400 hover:text-red-300"
              onClick={() => removeReview(mine)}
            >
              🗑 Delete
            </button>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="card mt-4 space-y-3">
          <p className="font-semibold text-white">
            {editingId
              ? editingDraft
                ? "Edit your draft"
                : editingScheduled
                  ? "Edit your scheduled review"
                  : "Edit your review"
              : isCritic
                ? "Write a Critic Review"
                : "Write a review"}
          </p>

          {isCritic && (
            <div className="rounded-lg border border-blue-500/30 bg-blue-950/40 p-3 text-xs text-blue-300">
              ✍️ Authoring as Verified Critic — add structured critique sections and media attachments below.
            </div>
          )}

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
            placeholder={isCritic ? "Your in-depth critique (min 10 words)" : "Your review (min 10 chars)"}
            value={form.content}
            minLength={10}
            required
            onChange={(e) => setForm({ ...form, content: e.target.value })}
          />

          {isCritic && (
            <div className="text-right text-xs text-slate-400">
              Total words:{" "}
              <span
                className={
                  countWords(form.content, form.sections) < 10 || countWords(form.content, form.sections) > 1000
                    ? "font-semibold text-amber-400"
                    : "font-semibold text-emerald-400"
                }
              >
                {countWords(form.content, form.sections)}
              </span>{" "}
              (10–1000 words required for critics)
            </div>
          )}

          {isCritic && (
            <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                  Review Sections (Structured critique)
                </p>
                <div className="flex flex-wrap gap-1">
                  {CRITIC_SECTION_OPTIONS.filter((sec) => !form.sections[sec]).map((sec) => (
                    <button
                      key={sec}
                      type="button"
                      onClick={() =>
                        setForm({
                          ...form,
                          sections: { ...form.sections, [sec]: "" },
                        })
                      }
                      className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700 hover:text-white"
                    >
                      + {sec}
                    </button>
                  ))}
                </div>
              </div>

              {Object.entries(form.sections).map(([sec, txt]) => (
                <div key={sec} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-300">{sec}</span>
                    <button
                      type="button"
                      onClick={() => {
                        const next = { ...form.sections };
                        delete next[sec];
                        setForm({ ...form, sections: next });
                      }}
                      className="text-red-400 hover:text-red-300"
                    >
                      ✕ Remove
                    </button>
                  </div>
                  <textarea
                    className="input min-h-[60px] text-xs"
                    placeholder={`Critique regarding ${sec}…`}
                    value={txt}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        sections: { ...form.sections, [sec]: e.target.value },
                      })
                    }
                  />
                </div>
              ))}
            </div>
          )}

          {isCritic && (
            <div>
              <label className="text-xs text-slate-300">
                Media Attachment (Trailer link, image, or video clip URL)
              </label>
              <input
                type="url"
                className="input mt-1"
                placeholder="https://youtube.com/watch?v=... or https://..."
                value={form.media_url}
                onChange={(e) => setForm({ ...form, media_url: e.target.value })}
              />
            </div>
          )}

          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={form.is_spoiler}
              onChange={(e) => setForm({ ...form, is_spoiler: e.target.checked })}
            />
            Contains spoilers
          </label>

          {showPublishOptions && (
            <fieldset className="space-y-2 rounded-lg border border-slate-800 p-3">
              <legend className="px-1 text-sm text-slate-300">
                {editingId ? "Status" : "When to publish"}
              </legend>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="publishMode"
                  checked={publishMode === "now"}
                  onChange={() => setPublishMode("now")}
                />
                {editingId ? "Publish now" : "Publish immediately"}
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="publishMode"
                  checked={publishMode === "later"}
                  onChange={() => {
                    setPublishMode("later");
                    if (!scheduleAt) {
                      setScheduleAt(toLocalInput(new Date(Date.now() + 60 * 60 * 1000)));
                    }
                  }}
                />
                Schedule for later
              </label>
              {publishMode === "later" && (
                <div>
                  <input
                    type="datetime-local"
                    className="input"
                    value={scheduleAt}
                    min={minScheduleInput()}
                    max={maxScheduleInput()}
                    required
                    onChange={(e) => setScheduleAt(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Hidden from everyone, and from the scores, until this time (
                    {Intl.DateTimeFormat().resolvedOptions().timeZone}).
                  </p>
                </div>
              )}
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="publishMode"
                  checked={publishMode === "draft"}
                  onChange={() => setPublishMode("draft")}
                />
                {editingScheduled
                  ? "Move back to draft"
                  : editingDraft
                    ? "Keep as draft"
                    : "Save as draft (only you can see it)"}
              </label>
            </fieldset>
          )}

          <button className="btn-primary" disabled={submitting}>
            {submitting
              ? "Saving…"
              : showPublishOptions && publishMode === "draft"
                ? "Save draft"
                : showPublishOptions && publishMode === "later"
                  ? editingId
                    ? "Save schedule"
                    : "Schedule review"
                  : editingId
                    ? showPublishOptions
                      ? "Publish now"
                      : "Save changes"
                    : "Submit review"}
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
            {audience === "verified"
              ? "No verified attendee has reviewed this event yet."
              : "No reviews yet — be the first to write one."}
          </div>
        ) : (
          data?.reviews.map((r) => {
            const isMine = !!profile?.id && String(profile.id) === String(r.user_id);
            return (
              <ReviewCard
                key={r.id}
                review={r}
                token={token}
                onChange={updateReview}
                canManage={Boolean(isAdmin) || isMine}
                isMine={isMine}
                hideSpoilers={hideSpoilers}
                onEdit={startEdit}
                onDelete={removeReview}
              />
            );
          })
        )}
      </div>
    </div>
  );
}