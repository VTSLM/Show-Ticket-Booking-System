import { api } from "./api";

export interface CancelEligibility {
  eligible: boolean;
  reason?: string;
  refund_amount?: number;
  has_payment?: boolean;
  show_start_time?: string;
  cancel_before?: string;
}

export interface CancelResult {
  status: string;
  refund_initiated: boolean;
  refund_amount: number;
  razorpay_refund_id: string | null;
  note: string;
}

export const cancellationsApi = {
  checkEligibility: (bookingId: string): Promise<CancelEligibility> =>
    api.get(`/api/bookings/${bookingId}/cancel-eligibility`),

  cancel: (bookingId: string): Promise<CancelResult> =>
    api.post(`/api/bookings/${bookingId}/cancel`, {}),
};
