import { auth } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  requireAuth = true
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (requireAuth) {
    const token = await getToken();
    if (!token) throw new Error("Not authenticated");
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string, auth = true) => request<T>("GET", path, undefined, auth),
  post: <T>(path: string, body?: unknown, auth = true) =>
    request<T>("POST", path, body, auth),
  put: <T>(path: string, body?: unknown, auth = true) =>
    request<T>("PUT", path, body, auth),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export const authApi = {
  register: (data: object) => api.post("/auth/register", data, false),
  verifyToken: (id_token: string) => api.post("/auth/verify-token", { id_token }, false),
  me: () => api.get("/auth/me"),
};

export const browseApi = {
  shows: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return api.get<any[]>(`/api/browse/shows${qs}`, false);
  },
  showDetail: (id: string) => api.get<any>(`/api/browse/shows/${id}`, false),
  cities: () => api.get<string[]>("/api/browse/cities", false),
};

export const seatsApi = {
  map: (showId: string) => api.get<any[]>(`/api/seats/${showId}/map`, false),
  lock: (showId: string, seat_ids: string[]) =>
    api.post(`/api/seats/${showId}/lock`, { seat_ids }),
  release: (showId: string, seat_ids: string[]) =>
    api.post(`/api/seats/${showId}/release`, { seat_ids }),
};

export const bookingsApi = {
  create: (show_id: string, seat_ids: string[]) =>
    api.post<any>("/api/bookings", { show_id, seat_ids }),
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

  shows: () => api.get<any[]>("/api/manager/shows"),
  createShow: (data: object) => api.post("/api/manager/shows", data),
  deleteShow: (id: string) => api.delete(`/api/manager/shows/${id}`),
};

export const adminApi = {
  pending: () => api.get<any[]>("/admin/pending"),
  approve: (user_id: string, action: string) =>
    api.post(`/admin/pending/${user_id}`, { action }),
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
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_URL}/api/verification/cases/${caseId}/documents`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Document upload failed");
    }
    return res.json();
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
    const token = await getToken();
    if (!token) throw new Error("Not authenticated");

    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);

    const response = await fetch(`${API_URL}/api/venue-verification/${caseId}/documents`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: form,
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.detail || "File upload failed");
    }

    return result;
  },

  download: async (caseId: string, documentId: string, filename: string) => {
    const token = await getToken();
    if (!token) throw new Error("Not authenticated");

    const response = await fetch(
      `${API_URL}/api/venue-verification/${caseId}/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

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
