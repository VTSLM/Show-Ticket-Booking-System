// Split & transfer tickets — API helper (backend: routers/ticket_transfers.py)
import { api, downloadFile } from "./api";

export type TransferStatus = "pending" | "accepted" | "declined" | "cancelled" | "expired";

export interface TransferSeat {
  booking_seat_id: string;
  label: string;
  seat_type: string;
  price: number;
  /** yours = still on your booking, pending = sent and waiting, transferred = friend accepted */
  state: "yours" | "pending" | "transferred";
  transfer_id: string | null;
}

export interface SentTransfer {
  id: string;
  status: TransferStatus;
  recipient_name: string;
  recipient_contact: string;
  seats: string[];
  used: boolean;
  requested_share_paise: number | null;
  demo_amount: number | null;
  demo_refund_status: "pending" | "processed" | "failed" | null;
  created_at: string | null;
  responded_at: string | null;
}

export interface BookingTransfers {
  booking_id: string;
  event_title: string;
  start_time: string | null;
  can_transfer: boolean;
  demo_payment_available: boolean;
  reason: string | null;
  seats: TransferSeat[];
  zones: { booking_zone_id: string; name: string; quantity: number; available: number }[];
  transfers: SentTransfer[];
}

export interface ReceivedTransfer {
  id: string;
  status: TransferStatus | "booking_cancelled";
  used: boolean;
  requested_share_paise: number | null;
  demo_amount: number | null;
  demo_refund_status: "pending" | "processed" | "failed" | null;
  sender_name: string;
  event_title: string;
  poster_url: string | null;
  start_time: string | null;
  venue_name: string;
  city: string;
  screen_name: string;
  seats: string[];
  /** true when this transfer was forwarded to you by someone who received it first */
  is_forward: boolean;
  /** seats you passed on to someone else (no longer on your QR) */
  forwarded_seats: string[];
  /** seats you still hold, with ids for the forward request */
  seat_items: { booking_seat_id: string; label: string; forwarded: boolean; forward_pending: boolean }[];
  can_forward: boolean;
  demo_payment_available: boolean;
  demo_refund_target: "buyer" | "recipient" | null;
  qr_data: string | null;
  qr_image: string | null; // base64 PNG
}

/** A booking with seats you still hold — the "Available" section. */
export interface AvailableBooking {
  booking_id: string;
  event_title: string;
  poster_url: string | null;
  start_time: string | null;
  venue_name: string;
  city: string;
  seats: string[];
  pending_count: number;
}

/** A transfer you made — the "Split" section. */
export interface SplitTransfer {
  id: string;
  booking_id: string;
  status: TransferStatus;
  used: boolean;
  is_forward: boolean;
  recipient_name: string;
  event_title: string;
  start_time: string | null;
  venue_name: string;
  city: string;
  seats: string[];
  created_at: string | null;
}

export interface TicketsOverview {
  available: AvailableBooking[];
  split: SplitTransfer[];
  received: ReceivedTransfer[];
}

export const transfersApi = {
  overview: () => api.get<TicketsOverview>("/api/transfers/overview"),
  forward: (id: string, data: { seat_ids: string[]; recipient: string }) =>
    api.post<{ id: string; status: TransferStatus; recipient_name: string; seats: string[]; message: string }>(
      `/api/transfers/${id}/forward`,
      data,
    ),
  forBooking: (bookingId: string) =>
    api.get<BookingTransfers>(`/api/transfers/booking/${bookingId}`),
  send: (data: { booking_id: string; seat_ids: string[]; zones: { booking_zone_id: string; quantity: number }[]; recipient: string; request_demo_payment?: boolean }) =>
    api.post<{ id: string; status: TransferStatus; recipient_name: string; seats: string[]; message: string }>(
      "/api/transfers",
      data,
    ),
  received: () => api.get<ReceivedTransfer[]>("/api/transfers/received"),
  demoCheckout: (id: string) => api.post<{ order_id: string; amount: number; currency: string; key_id: string }>(
    `/api/transfers/${id}/demo-checkout`,
  ),
  checkDemoCheckout: (id: string) => api.post<{ status: string }>(`/api/transfers/${id}/demo-checkout/check`),
  accept: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/accept`),
  decline: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/decline`),
  cancel: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/cancel`),
  /** PDF ticket with the recipient's own QR (accepted transfers only). */
  pdf: (id: string) => downloadFile(`/api/transfers/${id}/pdf`),
};

export const TRANSFER_STATUS_STYLES: Record<string, { label: string; color: string }> = {
  pending: { label: "Waiting for reply", color: "#ffb300" },
  accepted: { label: "Accepted", color: "#00c977" },
  declined: { label: "Declined", color: "#ff5566" },
  cancelled: { label: "Cancelled", color: "#9ba3b5" },
  expired: { label: "Expired", color: "#9ba3b5" },
  booking_cancelled: { label: "Booking cancelled", color: "#ff5566" },
};
