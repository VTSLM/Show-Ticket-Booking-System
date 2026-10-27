export type SeatStatus = 'available' | 'selected' | 'locked' | 'booked' | 'reserved';
export type SeatType = 'standard' | 'premium' | 'accessible';

export interface SeatItem {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: SeatType;
  price: number;
  status: SeatStatus;
  is_mine: boolean;
}

export interface ShowDetails {
  id: string;
  title: string;
  language: string;
  genre: string;
  duration: number; // in minutes
  poster_url?: string | null;
  venue: string;
  city: string;
  screen: string;
  start_time: string; // ISO 8601 UTC
  status: 'scheduled' | 'cancelled' | 'completed';
}

export interface MyHoldSummary {
  booking_id: string;
  booking_number: string;
  expires_at: string;
  show_seat_ids: string[];
  total_amount: number;
}

export interface SeatMapData {
  server_time: string;
  show: ShowDetails;
  max_seats_per_booking: number;
  bookable: boolean;
  bookable_reason?: string | null;
  my_hold?: MyHoldSummary | null;
  seats: SeatItem[];
}

export interface GridSeat {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: SeatType;
  price: number;
  status: SeatStatus;
  is_mine: boolean;
  is_aisle: boolean;
}

export interface GridRow {
  row_label: string;
  seat_type: SeatType;
  price: number;
  seats: GridSeat[];
}

export interface RowBand {
  title: string;
  seat_type: SeatType;
  price: number;
  rows: GridRow[];
}
