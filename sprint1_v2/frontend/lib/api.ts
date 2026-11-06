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
  get:    <T>(path: string, auth = true) => request<T>("GET", path, undefined, auth),
  post:   <T>(path: string, body?: unknown, auth = true) => request<T>("POST", path, body, auth),
  patch:  <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// Typed helpers
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
  lock: (showId: string, seat_ids: string[]) => api.post(`/api/seats/${showId}/lock`, { seat_ids }),
  release: (showId: string, seat_ids: string[]) => api.post(`/api/seats/${showId}/release`, { seat_ids }),
};

export const bookingsApi = {
  create: (show_id: string, seat_ids: string[]) => api.post<any>("/api/bookings", { show_id, seat_ids }),
  get: (id: string) => api.get<any>(`/api/bookings/${id}`),
  list: () => api.get<any[]>("/api/bookings"),
};

export const paymentsApi = {
  createOrder: (booking_id: string) => api.post<any>("/api/payments/orders", { booking_id }),
  verify: (booking_id: string, data: object) => api.post<any>(`/api/payments/orders/${booking_id}/verify`, data),
};

export const ticketsApi = {
  confirm: (booking_id: string) => api.post<any>(`/api/tickets/bookings/${booking_id}/confirm`),
  pdfUrl: (booking_id: string) => `${API_URL}/api/tickets/bookings/${booking_id}/pdf`,
  verify: (booking_id: string) => api.get<any>(`/api/tickets/bookings/${booking_id}/verify`, false),
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

  shows: () => api.get<any[]>("/api/manager/shows"),
  createShow: (data: object) => api.post("/api/manager/shows", data),
  deleteShow: (id: string) => api.delete(`/api/manager/shows/${id}`),
};

export const adminApi = {
  pending: () => api.get<any[]>("/admin/pending"),
  approve: (user_id: string, action: string) => api.post(`/admin/pending/${user_id}`, { action }),
};
