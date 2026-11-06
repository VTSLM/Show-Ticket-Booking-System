const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function req<T>(
  path: string,
  init?: RequestInit
): Promise<T> {

  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const body = await response.json();

      if (body.detail) {
        message = body.detail;
      } else if (body.message) {
        message = body.message;
      }
    } catch {
      // Keep HTTP status as fallback
    }

    throw new Error(message);
  }

  return response.json();
}

export type Seat = {
  id: string;
  row_index: number;
  col_index: number;
  label: string;
  category: string | null;
  price: number | null;
  status: 'available' | 'blocked';
};

export type Layout = {
  id: string;
  screen_id: string | null;
  screen_name: string;
  rows: number;
  columns: number;
  approved_capacity: number;
  status: string;
  seats: Seat[];
};

export type Screen = {
  id: string;
  name: string;
};

export const getScreens = () =>
  req<Screen[]>('/api/screens');

export const listLayouts = () =>
  req<Layout[]>('/api/layouts');

export const createLayout = (payload: unknown) =>
  req<Layout>('/api/layouts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const updateLayout = (
  id: string,
  payload: unknown
) =>
  req<Layout>(`/api/layouts/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });

export const bulkUpdate = (
  id: string,
  payload: unknown
) =>
  req<Layout>(`/api/layouts/${id}/bulk-update`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const getFixture = (id: string) =>
  req<unknown>(`/api/layouts/${id}/fixture`);