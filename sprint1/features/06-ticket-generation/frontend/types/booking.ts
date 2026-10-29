export interface SeatInfo {
  seat_id: string;
  row: string;
  number: number;
  tier: string;
  price: number;
}

export interface BookingConfirmation {
  status: string;
  booking_id: string;
  transaction_id: string;
  user: {
    user_id: string;
    name: string;
    email: string;
  };
  event: {
    event_id: string;
    name: string;
    date: string;
    time: string;
    venue: string;
  };
  seats: SeatInfo[];
  total_amount: number;
  booked_at: string;
  qr_code_base64: string;
  email_sent: boolean;
  pdf_download_url: string;
}
