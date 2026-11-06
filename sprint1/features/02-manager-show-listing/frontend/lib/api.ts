import {
  CreateEventPayload,
  CreateShowPayload,
  CreateVenuePayload,
  CreateScreenInput,
  EventItem,
  ScreenItem,
  SeatCountInfo,
  ShowHandoffData,
  ShowItem,
  VenueItem,
} from "./types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

let authToken: string | null = null;

export function setClientAuthToken(token: string | null) {
  authToken = token;
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  } else {
    // Development bypass header for testing with seed data
    headers["X-Dev-Firebase-Uid"] = "DEV_FIREBASE_UID_MANAGER";
  }

  return headers;
}

export async function fetchHealth() {
  const res = await fetch(`${BACKEND_URL}/api/manager/health`);
  return res.json();
}

export async function fetchEvents(): Promise<EventItem[]> {
  const res = await fetch(`${BACKEND_URL}/api/manager/events`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch events" }));
    throw new Error(error.detail || "Failed to fetch events");
  }
  return res.json();
}

export async function createEvent(payload: CreateEventPayload): Promise<EventItem> {
  const res = await fetch(`${BACKEND_URL}/api/manager/events`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create event" }));
    throw new Error(error.detail || "Failed to create event");
  }
  return res.json();
}

export async function fetchVenues(): Promise<VenueItem[]> {
  const res = await fetch(`${BACKEND_URL}/api/manager/venues`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch venues" }));
    throw new Error(error.detail || "Failed to fetch venues");
  }
  return res.json();
}

export async function createVenue(payload: CreateVenuePayload): Promise<VenueItem> {
  const res = await fetch(`${BACKEND_URL}/api/manager/venues`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create cinema venue" }));
    throw new Error(error.detail || "Failed to create cinema venue");
  }
  return res.json();
}

export async function createVenueScreen(venueId: string, payload: CreateScreenInput): Promise<ScreenItem> {
  const res = await fetch(`${BACKEND_URL}/api/manager/venues/${venueId}/screens`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to add screen" }));
    throw new Error(error.detail || "Failed to add screen");
  }
  return res.json();
}

export async function fetchScreenSeatCount(screenId: string): Promise<SeatCountInfo> {
  const res = await fetch(
    `${BACKEND_URL}/api/manager/screens/${screenId}/seat-count`,
    {
      headers: getHeaders(),
    }
  );
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch seat count" }));
    throw new Error(error.detail || "Failed to fetch seat count");
  }
  return res.json();
}

export async function fetchShows(): Promise<ShowItem[]> {
  const res = await fetch(`${BACKEND_URL}/api/manager/shows`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch shows" }));
    throw new Error(error.detail || "Failed to fetch shows");
  }
  return res.json();
}

export async function createShow(payload: CreateShowPayload): Promise<ShowItem> {
  const res = await fetch(`${BACKEND_URL}/api/manager/shows`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to schedule show" }));
    throw new Error(error.detail || "Failed to schedule show");
  }
  return res.json();
}

export async function fetchShowHandoff(showId: string): Promise<ShowHandoffData> {
  const res = await fetch(`${BACKEND_URL}/api/manager/shows/${showId}/handoff`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch handoff data" }));
    throw new Error(error.detail || "Failed to fetch handoff data");
  }
  return res.json();
}

export async function deleteEvent(eventId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/manager/events/${eventId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete movie" }));
    throw new Error(error.detail || "Failed to delete movie");
  }
}

export async function deleteShow(showId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/manager/shows/${showId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete show" }));
    throw new Error(error.detail || "Failed to delete show");
  }
}

export async function deleteVenue(venueId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/manager/venues/${venueId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete cinema venue" }));
    throw new Error(error.detail || "Failed to delete cinema venue");
  }
}
