// Split & transfer tickets — API helper (backend: routers/ticket_transfers.py)
import { api } from "./api";

export type TransferStatus = "pending" | "accepted" | "declined" | "cancelled";

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
  created_at: string | null;
  responded_at: string | null;
}

export interface BookingTransfers {
  booking_id: string;
  event_title: string;
  start_time: string | null;
  can_transfer: boolean;
  reason: string | null;
  seats: TransferSeat[];
  transfers: SentTransfer[];
}

export interface ReceivedTransfer {
  id: string;
  status: TransferStatus | "booking_cancelled";
  used: boolean;
  sender_name: string;
  event_title: string;
  poster_url: string | null;
  start_time: string | null;
  venue_name: string;
  city: string;
  screen_name: string;
  seats: string[];
  qr_data: string | null;
  qr_image: string | null; // base64 PNG
}

export const transfersApi = {
  forBooking: (bookingId: string) =>
    api.get<BookingTransfers>(`/api/transfers/booking/${bookingId}`),
  send: (data: { booking_id: string; seat_ids: string[]; recipient: string }) =>
    api.post<{ id: string; status: TransferStatus; recipient_name: string; seats: string[]; message: string }>(
      "/api/transfers",
      data,
    ),
  received: () => api.get<ReceivedTransfer[]>("/api/transfers/received"),
  accept: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/accept`),
  decline: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/decline`),
  cancel: (id: string) => api.post<{ id: string; status: TransferStatus }>(`/api/transfers/${id}/cancel`),
};

export const TRANSFER_STATUS_STYLES: Record<string, { label: string; color: string }> = {
  pending: { label: "Waiting for reply", color: "#ffb300" },
  accepted: { label: "Accepted", color: "#00c977" },
  declined: { label: "Declined", color: "#ff5566" },
  cancelled: { label: "Cancelled", color: "#9ba3b5" },
  booking_cancelled: { label: "Booking cancelled", color: "#ff5566" },
};
