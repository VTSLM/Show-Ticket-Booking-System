// lib/supportAdminApi.ts
// Customer Care — Admin-side API helpers (backend: routers/support_admin.py)
// Hari, Sprint 2 — items 5 & 6

import { api } from "./api";
import type {
  SupportRequestSummary,
  SupportRequestDetail,
  SupportStatus,
  SupportCategory,
} from "./supportApi";

// Re-export shared types so admin pages only import from here
export type { SupportStatus, SupportCategory, SupportRequestSummary, SupportRequestDetail };
export { CATEGORY_LABELS, STATUS_LABELS, STATUS_STYLES, formatDateTime } from "./supportApi";

export interface AdminListFilters {
  status?: SupportStatus;
  category?: SupportCategory;
  search?: string;
}

export interface AdminReplyBody {
  message: string;
  status?: SupportStatus; // optional status change with the reply
}

export interface AdminReplyResult {
  id: string;
  message: string;
  is_admin: true;
  sender_name: string;
  created_at: string;
  new_status: SupportStatus;
}

export const supportAdminApi = {
  /**
   * List all support requests with optional filters.
   * GET /api/admin/support/requests
   */
  list: (filters?: AdminListFilters) => {
    const params = new URLSearchParams();
    if (filters?.status)   params.set("status", filters.status);
    if (filters?.category) params.set("category", filters.category);
    if (filters?.search)   params.set("search", filters.search);
    const qs = params.toString();
    return api.get<SupportRequestSummary[]>(
      `/api/admin/support/requests${qs ? `?${qs}` : ""}`
    );
  },

  /**
   * Get a single request with full message thread.
   * GET /api/admin/support/requests/:id
   */
  get: (id: string) =>
    api.get<SupportRequestDetail>(`/api/admin/support/requests/${id}`),

  /**
   * Post an admin reply (optionally changes status).
   * POST /api/admin/support/requests/:id/reply
   */
  reply: (id: string, body: AdminReplyBody) =>
    api.post<AdminReplyResult>(`/api/admin/support/requests/${id}/reply`, body),

  /**
   * Change status without a message.
   * PATCH /api/admin/support/requests/:id/status
   */
  setStatus: (id: string, status: SupportStatus) =>
    api.patch<{ status: SupportStatus }>(
      `/api/admin/support/requests/${id}/status`,
      { status }
    ),
};
