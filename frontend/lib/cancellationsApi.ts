import { api } from "./api";

export interface CancelEligibilityBreakdown {
  ticket_amount: number;
  cancellation_charge: number;
  expected_refund: number;
  has_payment: boolean;
  cutoff_time: string;
  policy_name: string;
  policy_description?: string;
}

export interface CancelEligibilityResponse {
  eligible: boolean;
  reason?: string;
  event_title?: string;
  venue_name?: string;
  venue_city?: string;
  start_time?: string;
  seats?: string[];
  total_seats?: number;
  total_paid?: number;
  breakdown?: CancelEligibilityBreakdown;
}

export interface CancelBookingRequest {
  reason: string;
  comments?: string;
}

export interface CancelBookingResponse {
  status: string;
  refund_status: string;
  refund_amount: number;
  cancellation_charge: number;
  razorpay_refund_id: string | null;
  message: string;
}

export interface RefundStatusResponse {
  booking_id: string;
  booking_status: string;
  refund_status: string;
  total_amount: number;
  cancellation_charge: number;
  refund_amount: number;
  cancelled_at: string | null;
  refund?: {
    id: string;
    amount: number;
    cancellation_charge: number;
    status: string;
    razorpay_payment_id: string | null;
    razorpay_refund_id: string | null;
    failure_reason: string | null;
    retry_count: number;
    created_at: string;
    completed_at: string | null;
  } | null;
}

export interface AdminCancellationItem {
  booking_id: string;
  total_amount: number;
  cancellation_charge: number;
  refund_amount: number;
  refund_status: string;
  cancellation_reason: string;
  cancellation_notes: string | null;
  cancelled_at: string | null;
  user_id: string;
  customer_name: string;
  customer_email: string;
  event_title: string;
  start_time: string;
  refund_id: string | null;
  detailed_refund_status: string | null;
  razorpay_refund_id: string | null;
  failure_reason: string | null;
  retry_count: number | null;
}

export const cancellationsApi = {
  checkEligibility: (bookingId: string): Promise<CancelEligibilityResponse> =>
    api.get(`/api/bookings/${bookingId}/cancel-eligibility`),

  cancel: (bookingId: string, req: CancelBookingRequest): Promise<CancelBookingResponse> =>
    api.post(`/api/bookings/${bookingId}/cancel`, req),

  getRefundStatus: (bookingId: string): Promise<RefundStatusResponse> =>
    api.get(`/api/bookings/${bookingId}/refund-status`),

  // Admin APIs
  listAdminCancellations: (params?: { search?: string; refund_status?: string }): Promise<AdminCancellationItem[]> => {
    const q = new URLSearchParams();
    if (params?.search) q.append("search", params.search);
    if (params?.refund_status) q.append("refund_status", params.refund_status);
    return api.get(`/api/bookings/admin/cancellations?${q.toString()}`);
  },

  retryRefund: (refundId: string, notes?: string): Promise<{ status: string; refund_status: string }> =>
    api.post(`/api/bookings/admin/refunds/${refundId}/retry`, { notes }),
};
