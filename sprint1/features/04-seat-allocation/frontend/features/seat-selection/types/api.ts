export type ErrorCode =
  | 'UNAUTHENTICATED'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'MAX_SEATS_EXCEEDED'
  | 'SHOW_NOT_BOOKABLE'
  | 'SEATS_UNAVAILABLE'
  | 'HOLD_EXPIRED'
  | 'SERVICE_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  | 'NETWORK_ERROR';

export interface ApiErrorDetail {
  code: ErrorCode;
  message: string;
  details?: any;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export interface HoldResponse {
  booking_id: string;
  booking_number: string;
  total_amount: number;
  show_seat_ids: string[];
  expires_at: string;
  server_time: string;
}

export interface HoldDetailResponse {
  booking_id: string;
  booking_number: string;
  show_id: string;
  show_seat_ids: string[];
  total_amount: number;
  expires_at: string;
  status: string;
  server_time: string;
}

export interface ReleaseResponse {
  success: boolean;
  message: string;
  booking_id: string;
}

export interface SimulatePaymentResponse {
  success: boolean;
  message: string;
  booking_id: string;
  status: string;
}
