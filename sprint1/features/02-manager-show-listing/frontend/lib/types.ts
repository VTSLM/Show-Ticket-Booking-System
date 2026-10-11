export type EventType = "movie" | "concert" | "theatre" | "other";
export type EventStatus = "draft" | "published" | "inactive";
export type ShowStatus = "scheduled" | "cancelled" | "completed";

export interface EventItem {
  id: string;
  title: string;
  description?: string | null;
  event_type: EventType;
  duration_minutes?: number | null;
  language?: string | null;
  genre?: string | null;
  poster_url?: string | null;
  status: EventStatus;
  created_at: string;
  updated_at: string;
}

export interface ScreenItem {
  id: string;
  venue_id: string;
  name: string;
  capacity: number;
}

export interface VenueItem {
  id: string;
  name: string;
  address?: string | null;
  city: string;
  state?: string | null;
  pincode?: string | null;
  screens?: ScreenItem[];
}

export interface SeatCountInfo {
  screen_id: string;
  screen_name: string;
  venue_id: string;
  venue_name: string;
  seat_count: number;
  source: "seats_table" | "layout_capacity" | "screens_capacity";
  screen_capacity: number;
  seats_table_count: number;
  layout_capacity?: number | null;
}

export interface ShowItem {
  id: string;
  event_id: string;
  screen_id: string;
  start_time: string;
  end_time: string;
  status: ShowStatus;
  created_at: string;
  updated_at: string;
  event_title?: string;
  event_type?: EventType;
  event_poster_url?: string | null;
  venue_id?: string;
  venue_name?: string;
  screen_name?: string;
  seat_count?: number;
  pricing_ready?: boolean;
}

export interface ShowHandoffData {
  show_id: string;
  event_id: string;
  event_title: string;
  venue_id: string;
  venue_name: string;
  screen_id: string;
  screen_name: string;
  start_time: string;
  end_time: string;
  status: string;
  seat_count: number;
  pricing_ready: boolean;
  pricing_route: string;
  integration_notes: string;
}

export interface CreateEventPayload {
  title: string;
  description?: string;
  event_type: EventType;
  duration_minutes?: number;
  language?: string;
  genre?: string;
  poster_url?: string;
  status?: EventStatus;
}

export interface CreateShowPayload {
  event_id: string;
  screen_id: string;
  start_time: string;
  end_time?: string;
}

export interface CreateScreenInput {
  name: string;
  capacity: number;
}

export interface CreateVenuePayload {
  name: string;
  address?: string;
  city: string;
  state?: string;
  pincode?: string;
  screens?: CreateScreenInput[];
}

