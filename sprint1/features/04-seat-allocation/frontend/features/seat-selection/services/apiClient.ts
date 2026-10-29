import { getIdToken } from './firebaseAuth';
import { SeatMapData } from '../types/seat';
import {
  HoldResponse,
  HoldDetailResponse,
  ReleaseResponse,
  SimulatePaymentResponse,
  ApiErrorDetail,
  ErrorCode
} from '../types/api';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  code: ErrorCode;
  details?: any;
  status: number;

  constructor(status: number, code: ErrorCode, message: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function buildHeaders(includeAuth: boolean = true, customHeaders: Record<string, string> = {}): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  };

  if (includeAuth) {
    const token = await getIdToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return (await res.json()) as T;
  }

  let errorDetail: ApiErrorDetail;
  try {
    const body = await res.json();
    if (body && body.error && body.error.code) {
      errorDetail = body.error;
    } else {
      errorDetail = {
        code: (res.status === 404 ? 'NOT_FOUND' : 'INTERNAL_ERROR') as ErrorCode,
        message: body?.message || 'A server error occurred. Please try again.',
        details: body?.detail || null,
      };
    }
  } catch (parseError) {
    errorDetail = {
      code: 'INTERNAL_ERROR',
      message: 'Unexpected response from server. Please try again.',
    };
  }

  throw new ApiError(res.status, errorDetail.code, errorDetail.message, errorDetail.details);
}

export const apiClient = {
  /**
   * Fetches seat map layout, show metadata, and user active hold.
   * Supports HTTP 304 Not Modified caching via ETag.
   */
  async getSeatMap(
    showId: string,
    etag?: string | null
  ): Promise<{ data: SeatMapData; etag: string; notModified: false } | { notModified: true }> {
    const customHeaders: Record<string, string> = {};
    if (etag) {
      customHeaders['If-None-Match'] = etag;
    }

    try {
      const headers = await buildHeaders(true, customHeaders);
      const res = await fetch(`${API_BASE_URL}/api/shows/${showId}/seat-map`, {
        method: 'GET',
        headers,
      });

      if (res.status === 304) {
        return { notModified: true };
      }

      const responseEtag = res.headers.get('ETag') || '';
      const data = await handleResponse<SeatMapData>(res);
      return { data, etag: responseEtag, notModified: false };
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        0,
        'NETWORK_ERROR',
        'Unable to reach booking servers. Please check your internet connection.'
      );
    }
  },

  /**
   * Atomically locks seats and creates a pending booking.
   * Requires Bearer token and Idempotency-Key.
   */
  async createHold(
    showId: string,
    seatIds: string[],
    idempotencyKey: string
  ): Promise<HoldResponse> {
    try {
      const headers = await buildHeaders(true, {
        'Idempotency-Key': idempotencyKey,
      });

      const res = await fetch(`${API_BASE_URL}/api/shows/${showId}/holds`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ show_seat_ids: seatIds }),
      });

      return await handleResponse<HoldResponse>(res);
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        0,
        'NETWORK_ERROR',
        'Unable to reach booking servers. Please check your internet connection.'
      );
    }
  },

  /**
   * Releases an active pending hold for the authenticated user.
   */
  async releaseHold(bookingId: string): Promise<ReleaseResponse> {
    try {
      const headers = await buildHeaders(true);
      const res = await fetch(`${API_BASE_URL}/api/holds/${bookingId}`, {
        method: 'DELETE',
        headers,
      });

      return await handleResponse<ReleaseResponse>(res);
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        0,
        'NETWORK_ERROR',
        'Unable to reach booking servers.'
      );
    }
  },

  /**
   * Best-effort hold release triggered on page unload via fetch keepalive.
   */
  releaseHoldKeepalive(bookingId: string, token?: string | null): void {
    if (typeof window === 'undefined') return;
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      fetch(`${API_BASE_URL}/api/holds/${bookingId}`, {
        method: 'DELETE',
        headers,
        keepalive: true,
      }).catch(() => {
        // Silently swallow unload network aborts
      });
    } catch (e) {
      // Best-effort safety net; DB lock expiry will clean up if this fails
    }
  },

  /**
   * Fetches hold details for checkout initialization.
   */
  async getHold(bookingId: string): Promise<HoldDetailResponse> {
    try {
      const headers = await buildHeaders(true);
      const res = await fetch(`${API_BASE_URL}/api/holds/${bookingId}`, {
        method: 'GET',
        headers,
      });

      return await handleResponse<HoldDetailResponse>(res);
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        0,
        'NETWORK_ERROR',
        'Unable to reach booking servers.'
      );
    }
  },

  /**
   * DEV ONLY: Simulates payment confirmation for local testing.
   */
  async simulatePayment(bookingId: string): Promise<SimulatePaymentResponse> {
    try {
      const headers = await buildHeaders(true);
      const res = await fetch(`${API_BASE_URL}/api/dev/simulate-payment/${bookingId}`, {
        method: 'POST',
        headers,
      });

      return await handleResponse<SimulatePaymentResponse>(res);
    } catch (err: any) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        0,
        'NETWORK_ERROR',
        'Unable to reach payment simulation endpoint.'
      );
    }
  },
};
