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
  version: number;
  published_at: string;
  updated_at: string;
  author: ReviewAuthor;
  upvotes_count: number;
  has_upvoted: boolean;
  comments_count: number;
  comments: ReviewComment[];
  versions_count: number;
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

export interface MyReview {
  id: string;
  rating: number;
  headline: string;
  content: string;
  is_spoiler: boolean;
  version: number;
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
      is_spoiler?: boolean;
    }
  ) {
    return request<Review>("", { method: "POST", token, body });
  },

  update(
    token: string,
    reviewId: string,
    body: { rating?: number; headline?: string; content?: string; is_spoiler?: boolean }
  ) {
    return request<Review>(`/${reviewId}`, { method: "PATCH", token, body });
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

  comment(token: string, reviewId: string, content: string) {
    return request<ReviewComment>(`/${reviewId}/comments`, {
      method: "POST",
      token,
      body: { content },
    });
  },
};
