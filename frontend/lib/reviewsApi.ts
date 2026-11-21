const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ReviewAuthor {
  id: string;
  name: string;
  email: string;
  role: string;
  is_verified: boolean;
  publication?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
}

export interface ReviewComment {
  id: string;
  review_id: string;
  user_id: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
  author_name: string;
  author_avatar?: string | null;
  is_critic: boolean;
  parent_comment_id?: string | null; // set on replies
  is_review_author?: boolean; // commenter wrote the review
}

export interface Review {
  id: string;
  event_id: string;
  user_id: string;
  rating: number;
  headline: string;
  content: string;
  sections?: Record<string, string> | null;
  media_url?: string | null;
  is_spoiler: boolean;
  is_draft: boolean;
  version: number;
  published_at: string;
  updated_at: string;
  author: ReviewAuthor;
  upvotes_count: number;
  has_upvoted: boolean;
  has_reported?: boolean; // current user already reported this review
  is_verified_attendee?: boolean; // reviewer holds a ticket for a show of this event
  watched_at?: string | null; // start time of the show the reviewer booked
  watched_venue?: string | null;
  watched_city?: string | null;
  comments_count: number;
  comments: ReviewComment[];
  versions_count: number;
  scheduled_for?: string | null;
}

export interface Aggregates {
  average_critic_score: number;
  critic_fresh_percentage: number;
  total_critic_reviews: number;
  average_user_score: number;
  user_fresh_percentage: number;
  total_user_reviews: number;
}

export interface EventReviews {
  event_id: string;
  aggregates: Aggregates;
  reviews: Review[];
}

export interface AiReviewSummary {
  event_id: string;
  cached: boolean;
  generated_at: string;
  review_count: number;
  audience_rating: number;
  critic_rating: number;
  overall_rating: number;
  audience_summary: string;
  critic_summary: string;
  overall_summary: string;
  audience_liked: string[];
  audience_disliked: string[];
  critic_liked: string[];
  critic_disliked: string[];
}

export interface CriticProfile {
  id: string;
  name: string;
  publication?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
  role: string;
  total_reviews: number;
  average_rating: number;
  fresh_percentage: number;
  rating_history: Record<string, number>;
  reviews: {
    id: string;
    event_id: string;
    event_title: string;
    event_poster?: string | null;
    event_genre?: string | null;
    rating: number;
    headline: string;
    content: string;
    sections?: Record<string, string> | null;
    media_url?: string | null;
    is_spoiler: boolean;
    published_at: string;
    upvotes_count: number;
  }[];
}

export interface MyReview {
  id: string;
  rating: number;
  headline: string;
  content: string;
  sections?: Record<string, string> | null;
  media_url?: string | null;
  is_spoiler: boolean;
  is_draft: boolean;
  version: number;
  scheduled_for: string | null;
  is_scheduled: boolean; // true while the review is waiting for its publish time
}

export type ReportReason = "spam" | "abusive" | "spoiler" | "off_topic" | "other";

export interface ReportedReview {
  review_id: string;
  event_id: string;
  event_title: string;
  author_name: string;
  rating: number;
  headline: string;
  content: string;
  is_spoiler: boolean;
  is_public: boolean;
  latest_report_at: string;
  open_count: number;
  reports: {
    id: string;
    reason: ReportReason;
    details: string | null;
    status: "open" | "dismissed" | "reviewed";
    reporter_name: string;
    created_at: string;
  }[];
}

export type SortBy = "newest" | "highest" | "lowest" | "helpful";
export type Audience = "all" | "critics" | "audience";

async function request<T>(
  path: string,
  opts: { method?: string; token?: string | null; body?: unknown } = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;

  const res = await fetch(`${API_URL}/api/reviews${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail))
        message = data.detail.map((d: any) => d.msg).join(", ");
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

export const reviewsApi = {
  aiSummary(eventId: string) {
    return request<AiReviewSummary>(`/events/${eventId}/ai-summary`);
  },

  forEvent(
    eventId: string,
    opts: { audience?: Audience; sortBy?: SortBy; token?: string | null } = {}
  ) {
    const params = new URLSearchParams();
    if (opts.audience === "critics") params.set("critic_only", "true");
    if (opts.audience === "audience") params.set("audience_only", "true");
    params.set("sort_by", opts.sortBy || "newest");
    return request<EventReviews>(`/events/${eventId}?${params}`, { token: opts.token });
  },

  mine(token: string, eventId: string) {
    return request<{ review: MyReview | null }>(`/events/${eventId}/mine`, { token });
  },

  submit(
    token: string,
    body: {
      event_id: string;
      rating: number;
      headline: string;
      content: string;
      sections?: Record<string, string> | null;
      media_url?: string | null;
      is_spoiler?: boolean;
      scheduled_for?: string | null; // ISO date-time; omit to publish now
      is_draft?: boolean; // save as a private draft instead of publishing
    }
  ) {
    return request<Review>("", { method: "POST", token, body });
  },

  update(
    token: string,
    reviewId: string,
    body: {
      rating?: number;
      headline?: string;
      content?: string;
      sections?: Record<string, string> | null;
      media_url?: string | null;
      is_spoiler?: boolean;
      scheduled_for?: string | null; // reschedule (only while still scheduled)
      publish_now?: boolean; // publish a draft / scheduled review immediately
      is_draft?: boolean; // keep as draft, or move a scheduled review back to draft
    }
  ) {
    return request<Review>(`/${reviewId}`, { method: "PATCH", token, body });
  },

  criticProfile(criticId: string) {
    return request<CriticProfile>(`/critics/${criticId}`);
  },

  remove(token: string, reviewId: string) {
    return request<{ deleted: boolean }>(`/${reviewId}`, { method: "DELETE", token });
  },

  toggleUpvote(token: string, reviewId: string) {
    return request<{ upvoted: boolean; upvotes_count: number }>(
      `/${reviewId}/upvote`,
      { method: "POST", token }
    );
  },

  comment(token: string, reviewId: string, content: string, parentCommentId?: string) {
    return request<ReviewComment>(`/${reviewId}/comments`, {
      method: "POST",
      token,
      body: parentCommentId
        ? { content, parent_comment_id: parentCommentId }
        : { content },
    });
  },

  report(token: string, reviewId: string, reason: ReportReason, details?: string) {
    return request<{ reported: boolean }>(`/${reviewId}/report`, {
      method: "POST",
      token,
      body: details?.trim() ? { reason, details: details.trim() } : { reason },
    });
  },

  // Manager / admin only
  reports(token: string, status: "open" | "all" = "open") {
    return request<{ items: ReportedReview[] }>(`/reports?status=${status}`, { token });
  },

  resolveReports(token: string, reviewId: string, status: "dismissed" | "reviewed") {
    return request<{ updated: number; status: string }>(`/reports/${reviewId}`, {
      method: "PATCH",
      token,
      body: { status },
    });
  },
};