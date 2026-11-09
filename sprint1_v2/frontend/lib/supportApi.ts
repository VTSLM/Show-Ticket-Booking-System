// Customer Care — customer-side API helpers (backend: routers/support.py)
import { api } from "./api";

export type SupportCategory = "payment" | "booking" | "refund" | "account" | "other";
export type SupportStatus = "open" | "in_progress" | "resolved" | "closed";

export interface SupportMessage {
  id: string;
  message: string;
  is_admin: boolean;
  sender_name: string;
  created_at: string;
}

export interface SupportRequestSummary {
  id: string;
  request_number: string;
  category: SupportCategory;
  subject: string;
  status: SupportStatus;
  priority: "low" | "normal" | "high";
  created_at: string;
  updated_at: string;
  booking_number: string | null;
  message_count: number;
  last_reply_by_admin: boolean | null;
}

export interface SupportRequestDetail extends SupportRequestSummary {
  booking_id: string | null;
  resolved_at: string | null;
  messages: SupportMessage[];
}

export interface CreateSupportRequestBody {
  category: SupportCategory;
  subject: string;
  message: string;
  booking_id?: string;
}

export const supportApi = {
  create: (body: CreateSupportRequestBody) =>
    api.post<{ id: string; request_number: string }>("/api/support/requests", body),
  list: (status?: SupportStatus) =>
    api.get<SupportRequestSummary[]>(`/api/support/requests${status ? `?status=${status}` : ""}`),
  get: (id: string) => api.get<SupportRequestDetail>(`/api/support/requests/${id}`),
  reply: (id: string, message: string) =>
    api.post<SupportMessage>(`/api/support/requests/${id}/messages`, { message }),
  reopen: (id: string, message: string) =>
    api.post<{ id: string; status: SupportStatus }>(`/api/support/requests/${id}/reopen`, { message }),
};

// ── Display helpers shared by the support pages ──

export const CATEGORY_LABELS: Record<SupportCategory, string> = {
  payment: "Payment issue",
  booking: "Booking issue",
  refund: "Refund request",
  account: "Account / login",
  other: "Something else",
};

export const STATUS_LABELS: Record<SupportStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const STATUS_STYLES: Record<SupportStatus, string> = {
  open: "bg-yellow-100 text-yellow-700",
  in_progress: "bg-blue-100 text-blue-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-gray-200 text-gray-600",
};

/** Categories where the customer must pick a booking (matches the backend rule). */
export const BOOKING_REQUIRED: SupportCategory[] = ["booking", "refund"];

export const formatDateTime = (ts: string) => {
  try {
    return new Date(ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return ts;
  }
};
