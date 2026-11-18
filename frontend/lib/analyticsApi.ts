// Manager / Organizer analytics — API helper (backend: routers/manager_analytics.py)
// The API path is /api/manager/insights (not "analytics") so ad/privacy blockers don't block it.
import { api } from "./api";

export interface AnalyticsSummary {
  revenue: number;
  gross_revenue: number;
  refunds: number;
  revenue_change_pct: number | null;
  tickets_sold: number;
  tickets_change_pct: number | null;
  confirmed_bookings: number;
  unique_buyers: number;
  avg_order_value: number;
  avg_group_size: number;
  avg_lead_days: number | null;
  avg_ticket_price: number;
  occupancy_pct: number | null;
  shows_in_period: number;
  cancellations: number;
  cancellation_rate_pct: number;
  avg_rating: number | null;
  reviews: number;
  wishlisted: number;
}

export interface PricingGroup {
  shows: number;
  tickets: number;
  revenue: number;
  occupancy: number;
  avg_ticket_price: number;
}

export interface ManagerAnalytics {
  scope: string;
  has_organization: boolean;
  range: { start: string; end: string; days: number; previous_start: string; previous_end: string };
  events: { id: string; title: string; event_type: string }[];
  summary: AnalyticsSummary;
  trend: { date: string; revenue: number; tickets: number }[];
  by_event: {
    event_id: string; title: string; event_type: string; revenue: number; gross_revenue: number; tickets: number;
    avg_ticket_price: number | null;
    shows: number; occupancy: number | null; rating: number | null; reviews: number; wishlisted: number;
  }[];
  upcoming_shows: {
    show_id: string; title: string; event_type: string; venue: string; screen: string; start_time: string;
    capacity: number; sold: number; occupancy: number; revenue: number; dynamic_pricing: boolean;
    base_price: number;
  }[];
  outcomes: { confirmed: number; pending: number; expired: number; cancelled: number };
  by_weekday: { day: string; tickets: number; revenue: number }[];
  by_time_slot: { slot: string; tickets: number; revenue: number }[];
  pricing_comparison: { dynamic: PricingGroup; fixed: PricingGroup };
  lead_time: { buckets: { label: string; bookings: number; tickets: number }[]; avg_days: number | null; median_days: number | null };
  sales_curve: { days_before: number; pct_sold: number }[];
  customers: {
    buyers: number; new: number; returning: number; repeat_buyers: number; repeat_rate_pct: number;
    cross_category: number; cross_category_pct: number; top_combos: { combo: string; customers: number }[];
  };
  alerts: { level: "good" | "warn" | "info"; text: string }[];
}

export interface EventAnalytics {
  range: { start: string; end: string };
  event: {
    id: string; title: string; event_type: string; status: string; poster_url: string | null;
    language: string | null; genre: string | null; duration_minutes: number | null;
  };
  shows: {
    show_id: string; start_time: string; status: string; upcoming: boolean; venue: string; screen: string;
    dynamic_pricing: boolean; base_price: number; avg_ticket_price: number | null;
    capacity: number; sold: number; occupancy: number;
    gross_revenue: number; refunds: number; revenue: number;
    tickets: number; cancelled: number; rating: number | null; rating_count: number;
  }[];
  totals: {
    gross_revenue: number; refunds: number; revenue: number; tickets: number;
    dynamic_shows: number; fixed_shows: number;
  };
  best_show_id: string | null;
  ratings: { average: number | null; count: number; distribution: { score: number; count: number }[] };
  latest_reviews: { rating: number; headline: string; content: string; author: string; at: string | null }[];
  wishlisted: number;
}

export interface AnalyticsQuery {
  days?: number;
  start?: string;
  end?: string;
  event_id?: string;
}

export const analyticsApi = {
  get: (q: AnalyticsQuery) => {
    const params = new URLSearchParams();
    if (q.start && q.end) {
      params.set("start", q.start);
      params.set("end", q.end);
    } else if (q.days) {
      params.set("days", String(q.days));
    }
    if (q.event_id) params.set("event_id", q.event_id);
    return api.get<ManagerAnalytics>(`/api/manager/insights?${params.toString()}`);
  },
  event: (eventId: string, q: AnalyticsQuery) => {
    const params = new URLSearchParams();
    if (q.start && q.end) {
      params.set("start", q.start);
      params.set("end", q.end);
    } else if (q.days) {
      params.set("days", String(q.days));
    }
    return api.get<EventAnalytics>(`/api/manager/insights/event/${eventId}?${params.toString()}`);
  },
};
