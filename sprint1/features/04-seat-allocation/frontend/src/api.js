/**
 * api.js
 * ======
 * All HTTP calls to the FastAPI backend.
 * PHASE-1: Backend URL is the local dev server.
 * PHASE-2+: Set VITE_API_URL in .env to point to deployed backend.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    const message = typeof err.detail === 'object'
      ? err.detail.message
      : err.detail || 'Request failed';
    const error = new Error(message);
    error.status = res.status;
    error.detail = err.detail;
    throw error;
  }
  return res.json();
}

export const api = {
  /** Fetch all seats for a show (Phase 2) */
  getSeats(showId) {
    return fetch(`${BASE_URL}/api/shows/${showId}/seats`).then(handleResponse);
  },

  /**
   * Atomic lock request (Phase 3)
   * Locks ALL requested seats or NONE — all-or-nothing.
   */
  lockSeats(showId, seatIds, userId) {
    return fetch(`${BASE_URL}/api/seats/lock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_id: showId, seat_ids: seatIds, user_id: userId }),
    }).then(handleResponse);
  },

  /** Manual release before timer expires (Phase 4) */
  releaseSeats(showId, seatIds, userId) {
    return fetch(`${BASE_URL}/api/seats/release`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_id: showId, seat_ids: seatIds, user_id: userId }),
    }).then(handleResponse);
  },

  /**
   * Post-payment confirmation (Phase 5)
   * Re-verifies lock still valid, then marks seats as booked.
   */
  confirmSeats(showId, seatIds, userId) {
    return fetch(`${BASE_URL}/api/seats/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ show_id: showId, seat_ids: seatIds, user_id: userId }),
    }).then(handleResponse);
  },

  /** Cancel a confirmed booking (FR13) */
  cancelBooking(bookingId, userId) {
    return fetch(`${BASE_URL}/api/bookings/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ booking_id: bookingId, user_id: userId }),
    }).then(handleResponse);
  },

  /** Get booking by ID */
  getBooking(bookingId, userId) {
    return fetch(`${BASE_URL}/api/bookings/${bookingId}?user_id=${userId}`).then(handleResponse);
  },

  /** Get all bookings for a user */
  getUserBookings(userId) {
    return fetch(`${BASE_URL}/api/users/${userId}/bookings`).then(handleResponse);
  },
};

/** WebSocket URL (Phase 6) */
export function getWsUrl(showId) {
  const wsBase = BASE_URL.replace(/^http/, 'ws');
  return `${wsBase}/ws/${showId}`;
}
