import { auth } from "./firebase";
import {
  friendlyApiMessage,
  friendlyFirebaseMessage,
  friendlyNetworkMessage,
} from "./errorMessages";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_STORAGE_KEY = "ticketflow_session_id";

let sessionExpiryHandler: (() => void) | null = null;

export function onSessionExpired(handler: () => void) {
  sessionExpiryHandler = handler;
}

export function getActiveSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

export function setActiveSessionId(sessionId: string | null) {
  if (typeof window === "undefined") return;
  if (sessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  } else {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }
}

async function getToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  requireAuth: boolean | "optional" = true
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json"};

  if (requireAuth) {
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    if (token) headers["Authorization"] = `Bearer ${token}`;
    else if (requireAuth !== "optional") throw new Error("Not authenticated");

    const sessionId = getActiveSessionId();
    if (sessionId) headers["X-Session-ID"] = sessionId;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (networkErr) {
    throw new Error(friendlyNetworkMessage(networkErr));
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const rawDetail = err.detail;
    if (
      res.status === 401 &&
      typeof rawDetail === "string" &&
      (rawDetail.toLowerCase().includes("inactivity") ||
        rawDetail.toLowerCase().includes("session") ||
        rawDetail.toLowerCase().includes("revoked"))
    ) {
      if (sessionExpiryHandler) {
        sessionExpiryHandler();
      }
    }
    throw new ApiError(res.status, friendlyApiMessage(res.status, rawDetail), rawDetail);
  }

  if (res.status === 204) return undefined as T;
  try {
    return await res.json();
  } catch {
    throw new Error("We received an unexpected response. Please try again.");
  }
}

/** GET a file (e.g. a PDF ticket) with the user's auth token. */
export async function downloadFile(path: string): Promise<Blob> {
  let token: string | null;
  try {
    token = await getToken();
  } catch (error) {
    throw new Error(friendlyFirebaseMessage(error));
  }
  if (!token) throw new Error("Not authenticated");
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const sessionId = getActiveSessionId();
  if (sessionId) headers["X-Session-ID"] = sessionId;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { headers });
  } catch (networkErr) {
    throw new Error(friendlyNetworkMessage(networkErr));
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(friendlyApiMessage(res.status, err.detail));
  }
  return res.blob();
}

export const api = {
  get: <T>(path: string, auth: boolean | "optional" = true) =>
    request<T>("GET", path, undefined, auth),
  post: <T>(path: string, body?: unknown, auth: boolean | "optional" = true) =>
    request<T>("POST", path, body, auth),
  put: <T>(path: string, body?: unknown, auth = true) =>
    request<T>("PUT", path, body, auth),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export const authApi = {
  register: (data: object) => api.post("/auth/register", data, false),
  verifyToken: (id_token: string, session_id?: string | null) =>
    api.post("/auth/verify-token", { id_token, session_id }, false),
  me: () => api.get("/auth/me"),
  heartbeat: (session_id?: string) =>
    api.post("/auth/session/heartbeat", { session_id }),
  logoutSession: (session_id?: string) =>
    api.post("/auth/session/logout", { session_id }, false),
  getSessionPolicy: () =>
    api.get<{
      customer_timeout_seconds: number;
      manager_timeout_seconds: number;
      admin_timeout_seconds: number;
      warning_lead_seconds: number;
    }>("/auth/session/policy", false),
};

export const browseApi = {
  shows: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return api.get<any[]>(`/api/browse/shows${qs}`, false);
  },
  showDetail: (id: string) => api.get<any>(`/api/browse/shows/${id}`, false),
  eventDetail: (id: string) => api.get<any>(`/api/browse/events/${id}`, false),
  cities: () => api.get<string[]>("/api/browse/cities", false),
  indiaCities: () =>
    api.get<{ name: string; state: string; lat: number; lng: number }[]>("/api/browse/india-cities", false),
};

export interface RecommendedEvent {
  event_id: string;
  title: string;
  event_type: string;
  genre: string | null;
  language: string | null;
  poster_url: string | null;
  next_show_time: string | null;
  city: string | null;
  price_from: number | null;
  avg_rating: number | null;
  review_count: number;
  link: string;
  match?: string[];
  reason?: string | null;
  recent_bookings?: number;
}

export interface RecommendationsResponse {
  personalized: boolean;
  recommended: RecommendedEvent[];
  trending: RecommendedEvent[];
  ai_reasons: boolean;
  fallback: "guest" | "no_history" | "ai_timeout" | "ai_unavailable" | "ai_off" | null;
  based_on: string[];
}

export interface UserPreferences {
  genres: string[];
  artists: string[];
  cities: string[];
  updated_at?: string | null;
}

export const recommendationsApi = {
  get: (near?: { lat: number; lng: number } | null) => {
    const qs = near ? `?lat=${near.lat}&lng=${near.lng}` : "";
    return api.get<RecommendationsResponse>(`/api/recommendations${qs}`, "optional");
  },
  recordView: (eventId: string) =>
    api.post<{ recorded: boolean }>(`/api/recommendations/views/${eventId}`),
  preferences: () => api.get<UserPreferences>("/api/recommendations/preferences"),
  savePreferences: (prefs: UserPreferences) =>
    api.put<UserPreferences>("/api/recommendations/preferences", prefs),
  preferenceOptions: () =>
    api.get<{ genres: string[]; artists: string[]; cities: string[] }>(
      "/api/recommendations/preference-options",
      false
    ),
};

export const wishlistApi = {
  list: () => api.get<any[]>("/api/wishlist"),
  ids: () => api.get<{ event_ids: string[] }>("/api/wishlist/ids"),
  add: (eventId: string) => api.post<{ wishlisted: boolean }>(`/api/wishlist/${eventId}`),
  remove: (eventId: string) => api.delete<{ wishlisted: boolean }>(`/api/wishlist/${eventId}`),
};

export const seatsApi = {
  map: (showId: string) => api.get<any>(`/api/seats/${showId}/map`, "optional"),
  terms: (showId: string) => api.get<any>(`/api/seats/${showId}/terms`, false),
  lock: (showId: string, seat_ids: string[]) =>
    api.post(`/api/seats/${showId}/lock`, { seat_ids }),
  release: (showId: string, seat_ids: string[]) =>
    api.post(`/api/seats/${showId}/release`, { seat_ids }),
  lockZone: (showId: string, zone_id: string, quantity: number) =>
    api.post<any>(`/api/seats/${showId}/lock-zone`, { zone_id, quantity }),
  releaseZone: (showId: string, zone_id: string, quantity: number) =>
    api.post<any>(`/api/seats/${showId}/release-zone`, { zone_id, quantity }),
};

export const bookingsApi = {
  joinWaitlist: (showId: string) =>
    api.post<{ status: string; position: number }>(`/api/bookings/waitlist/${showId}`),
  myWaitlist: () => api.get<any[]>("/api/bookings/waitlist"),
  leaveWaitlist: (showId: string) =>
    api.delete<{ status: string }>(`/api/bookings/waitlist/${showId}`),
  create: (data: {
    show_id: string;
    seat_ids?: string[];
    zone_id?: string;
    zone_quantity?: number;
    terms_accepted?: boolean;
    terms_hash?: string;
    terms_text?: string;
    coupon_code?: string;
  } | string, maybeSeatIds?: string[]) => {
    if (typeof data === "string") {
      return api.post<any>("/api/bookings", { show_id: data, seat_ids: maybeSeatIds || [] });
    }
    return api.post<any>("/api/bookings", data);
  },
  acceptTerms: (bookingId: string, data: { terms_hash: string; terms_text: string }) =>
    api.post<any>(`/api/bookings/${bookingId}/accept-terms`, data),
  get: (id: string) => api.get<any>(`/api/bookings/${id}`),
  list: () => api.get<any[]>("/api/bookings"),
};

export const paymentsApi = {
  createOrder: (booking_id: string) =>
    api.post<any>("/api/payments/orders", { booking_id }),
  verify: (booking_id: string, data: object) =>
    api.post<any>(`/api/payments/orders/${booking_id}/verify`, data),
};

export const ticketsApi = {
  confirm: (booking_id: string) =>
    api.post<any>(`/api/tickets/bookings/${booking_id}/confirm`),
  pdfUrl: (booking_id: string) => `${API_URL}/api/tickets/bookings/${booking_id}/pdf`,
  verify: (booking_id: string) =>
    api.get<any>(`/api/tickets/bookings/${booking_id}/verify`, false),
  scan: (data: { qr_data?: string; booking_id?: string }) =>
    api.post<any>("/api/tickets/scan", data),
};

export const managerApi = {
  venues: () => api.get<any[]>("/api/manager/venues"),
  createVenue: (data: object) => api.post("/api/manager/venues", data),

  screens: (venueId: string) =>
    api.get<any[]>(`/api/manager/venues/${venueId}/screens`),

  createScreen: (venueId: string, data: object) =>
    api.post<any>(`/api/manager/venues/${venueId}/screens`, data),

  events: () => api.get<any[]>("/api/manager/events"),
  createEvent: (data: object) => api.post("/api/manager/events", data),
  updateEvent: (id: string, data: object) => api.patch<any>("/api/manager/events/" + id, data),
  // Poster or backdrop for an event (#169): returns the public URL to save on the event
  uploadEventImage: async (kind: "poster" | "backdrop", file: File): Promise<{ url: string }> => {
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    if (!token) throw new Error("Not authenticated");

    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    const sessionId = getActiveSessionId();
    if (sessionId) headers["X-Session-ID"] = sessionId;

    let response: Response;
    try {
      response = await fetch(`${API_URL}/api/manager/event-images`, { method: "POST", headers, body: form });
    } catch (error) {
      throw new Error(friendlyNetworkMessage(error));
    }
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(friendlyApiMessage(response.status, result.detail));
    }
    return response.json();
  },

  shows: () => api.get<any[]>("/api/manager/shows"),
  createShow: (data: object) => api.post<any>("/api/manager/shows", data),
  deleteShow: (id: string) => api.delete(`/api/manager/shows/${id}`),
  setDynamicPricing: (id: string, enabled: boolean) =>
    api.patch<any>(`/api/manager/shows/${id}`, { dynamic_pricing: enabled }),

  coupons: () => api.get<any[]>("/api/manager/coupons"),
  createCoupon: (data: { code: string; percent_off: number }) =>
    api.post<any>("/api/manager/coupons", data),
  setCouponActive: (code: string, is_active: boolean) =>
    api.patch<any>(`/api/manager/coupons/${encodeURIComponent(code)}`, { is_active }),

  updateSeatTier: (screenId: string, data: { row_label?: string; seat_ids?: string[]; seat_type: string }) =>
    api.put<any>(`/api/manager/screens/${screenId}/seats/tier`, data),
  getShowZones: (showId: string) =>
    api.get<any[]>(`/api/manager/shows/${showId}/zones`),
  addShowZone: (showId: string, data: object) =>
    api.post<any>(`/api/manager/shows/${showId}/zones`, data),
  deleteShowZone: (showId: string, zoneId: string) =>
    api.delete(`/api/manager/shows/${showId}/zones/${zoneId}`),
};

export const adminApi = {
  pending: () => api.get<any[]>("/admin/pending"),
  approve: (user_id: string, action: string) =>
    api.post(`/admin/pending/${user_id}`, { action }),
};

export type AdminUserRole = "customer" | "manager" | "admin";
export type AdminUserStatus = "active" | "inactive" | "blocked";

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  status: AdminUserStatus;
  roles: AdminUserRole[];
  created_at: string;
}

export interface AdminAuditEntry {
  id: string;
  action: "role_added" | "role_removed" | "status_changed" | "manager_approved" | "manager_rejected";
  details: Record<string, string>;
  reason: string | null;
  created_at: string;
  admin_name: string | null;
  admin_email: string | null;
}

export interface AdminUserList {
  users: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export const adminUsersApi = {
  list: (params: { q?: string; role?: string; status?: string; page?: number; page_size?: number }) => {
    const sp = new URLSearchParams();
    if (params.q) sp.append("q", params.q);
    if (params.role) sp.append("role", params.role);
    if (params.status) sp.append("status", params.status);
    if (params.page) sp.append("page", String(params.page));
    if (params.page_size) sp.append("page_size", String(params.page_size));
    const qs = sp.toString();
    return api.get<AdminUserList>(`/api/admin/users${qs ? `?${qs}` : ""}`);
  },
  get: (userId: string) =>
    api.get<AdminUser & { history: AdminAuditEntry[] }>(`/api/admin/users/${userId}`),
  changeRole: (userId: string, role: "manager" | "admin", action: "add" | "remove", reason: string) =>
    api.patch<AdminUser>(`/api/admin/users/${userId}/roles`, { role, action, reason }),
  changeStatus: (userId: string, status: "active" | "blocked", reason: string) =>
    api.patch<AdminUser>(`/api/admin/users/${userId}/status`, { status, reason }),
};

export const organizerVerificationApi = {
  checklist: (businessType: string) =>
    api.get<any>(`/api/verification/organizer/checklist?business_type=${businessType}`),
  myApplications: () =>
    api.get<any[]>("/api/verification/organizer/applications/me"),
  saveDraft: (data: object) =>
    api.post<any>("/api/verification/organizer/applications", data),
  submit: (applicationId: string) =>
    api.post<any>(`/api/verification/organizer/applications/${applicationId}/submit`),
  uploadDocument: async (caseId: string, formData: FormData) => {
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/verification/cases/${caseId}/documents`, {
        method: "POST",
        headers,
        body: formData,
      });
    } catch (error) {
      throw new Error(friendlyNetworkMessage(error));
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(friendlyApiMessage(res.status, err.detail || undefined));
    }
    try {
      return await res.json();
    } catch {
      throw new Error("We received an unexpected response. Please try again.");
    }
  },
  getViewUrl: (documentId: string) =>
    api.get<any>(`/api/verification/documents/${documentId}/view`),
  listDocuments: (caseId: string) =>
    api.get<any[]>(`/api/verification/cases/${caseId}/documents`),
  getMyPayoutEligibility: () =>
    api.get<any>("/api/verification/organizer/payout-eligibility"),
};

export const organizerAdminApi = {
  getReviewQueue: (status?: string) =>
    api.get<any>(`/api/admin/organizers/reviews${status ? `?status=${status}` : ""}`),
  getWorkspace: (id: string) =>
    api.get<any>(`/api/admin/organizers/${id}`),
  claimCase: (id: string) =>
    api.post<any>(`/api/admin/organizers/${id}/claim`),
  releaseCase: (id: string) =>
    api.post<any>(`/api/admin/organizers/${id}/release`),
  reviewDocument: (documentId: string, review_status: string, reviewer_comment?: string) =>
    api.post<any>(`/api/admin/organizers/documents/${documentId}/review`, {
      review_status,
      reviewer_comment,
    }),
  makeDecision: (
    id: string,
    decision: string,
    comments?: string,
    rejection_reason?: string
  ) =>
    api.post<any>(`/api/admin/organizers/${id}/decision`, {
      decision,
      comments,
      rejection_reason,
    }),
  listOrganizers: (params?: { q?: string; status?: string; tier?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.append("q", params.q);
    if (params?.status) sp.append("status", params.status);
    if (params?.tier) sp.append("tier", params.tier);
    if (params?.limit) sp.append("limit", params.limit.toString());
    if (params?.offset) sp.append("offset", params.offset.toString());
    const qs = sp.toString();
    return api.get<any>(`/api/admin/organizers${qs ? `?${qs}` : ""}`);
  },
  suspendOrganizer: (id: string, reason: string) =>
    api.post<any>(`/api/admin/organizers/${id}/suspend`, { reason }),
  reactivateOrganizer: (id: string, reason: string) =>
    api.post<any>(`/api/admin/organizers/${id}/reactivate`, { reason }),
  getPayoutEligibility: (id: string) =>
    api.get<any>(`/api/admin/organizers/${id}/payout-eligibility`),
};

type VenueVerificationDraft = {
  name: string;
  address?: string;
  city: string;
  state?: string;
  pincode?: string;
  licensed_capacity?: number | null;
  license_expiry?: string | null;
  noc_expiry?: string | null;
  latitude?: number | null;
  longitude?: number | null;
};

export const venueVerificationApi = {
  mine: () => api.get<any[]>("/api/venue-verification/mine"),
  create: (data: VenueVerificationDraft) =>
    api.post<any>("/api/venue-verification", data),
  update: (caseId: string, data: VenueVerificationDraft) =>
    api.put<any>(`/api/venue-verification/${caseId}`, data),
  submit: (caseId: string) =>
    api.post<any>(`/api/venue-verification/${caseId}/submit`),
  queue: () => api.get<any[]>("/api/venue-verification/admin/queue"),
  claim: (caseId: string) =>
    api.post<any>(`/api/venue-verification/admin/${caseId}/claim`),
  details: (caseId: string) =>
    api.get<any>(`/api/venue-verification/admin/${caseId}`),
  decide: (
    caseId: string,
    data: { expected_version: number; decision: string; reason?: string }
  ) => api.post<any>(`/api/venue-verification/admin/${caseId}/decision`, data),
  audit: (caseId: string) =>
    api.get<any[]>(`/api/venue-verification/admin/${caseId}/audit`),
};

export const venueDocumentsApi = {
  list: (caseId: string) =>
    api.get<any[]>(`/api/venue-verification/${caseId}/documents`),

  upload: async (caseId: string, kind: "venue_photo" | "seating_plan", file: File) => {
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    if (!token) throw new Error("Not authenticated");

    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);

    let response: Response;
    try {
      response = await fetch(`${API_URL}/api/venue-verification/${caseId}/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
    } catch (error) {
      throw new Error(friendlyNetworkMessage(error));
    }

    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(friendlyApiMessage(response.status, result.detail));
    }

    try {
      return await response.json();
    } catch {
      throw new Error("We received an unexpected response. Please try again.");
    }
  },

  download: async (caseId: string, documentId: string, filename: string) => {
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    if (!token) throw new Error("Not authenticated");

    let response: Response;
    try {
      response = await fetch(
        `${API_URL}/api/venue-verification/${caseId}/documents/${documentId}/download`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (error) {
      throw new Error(friendlyNetworkMessage(error));
    }

    if (!response.ok) {
      throw new Error("Could not download attachment");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatContext {
  event_id?: string;
  show_id?: string;
  booking_id?: string;
}

export interface ChatResultCard {
  show_id: string;
  event_id: string;
  title: string;
  poster_url?: string | null;
  time: string;
  venue: string;
  city: string;
  price_from?: string | null;
  seats_left: number;
  book_link: string;
}

export type ChatStreamEvent =
  | { type: "status"; tool: string; text: string }
  | { type: "delta"; text: string }
  | { type: "cards"; cards: ChatResultCard[] }
  | { type: "done"; reply_id: string; truncated?: boolean }
  | { type: "error"; message: string};

export const chatApi = {
  // The assistant is for logged-in users only (#204); the login token lets it see the user's own bookings
  send: (message: string, history: ChatMessage[], context: ChatContext) =>
    api.post<{ reply: string }>("/api/chat", { message, history, context }),

  /** Streams the reply as server-sent events; calls onEvent for each one. */
  stream: async (
    message: string,
    history: ChatMessage[],
    context: ChatContext,
    onEvent: (event: ChatStreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const headers: Record<string, string> = { "Content-Type": "application/json"};
    let token: string | null;
    try {
      token = await getToken();
    } catch (error) {
      throw new Error(friendlyFirebaseMessage(error));
    }
    if (token) headers["Authorization"] = `Bearer ${token}`;
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message, history, context }),
        signal,
      });
    } catch (error) {
      throw new Error(friendlyNetworkMessage(error));
    }
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({}));
      throw new Error(friendlyApiMessage(res.status, err.detail));
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)) as ChatStreamEvent);
      }
    }
  },

  feedback: (replyId: string, rating: 1 | -1) =>
    api.post<{ ok: boolean }>("/api/chat/feedback", {
      reply_id: replyId,
      rating,
    }, "optional"),
};