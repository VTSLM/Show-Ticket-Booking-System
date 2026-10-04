const TZ = 'Asia/Kolkata'; // matches backend DEFAULT_TIMEZONE
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function get(path, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''));
  const res = await fetch(`${BASE}${path}?${q}`);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error?.message || 'Something went wrong');
  return body;
}
export const getCities = (q) => get('/locations/cities', { q });
export const getShows = (p) => get('/shows', { page_size: 100, ...p });
export const searchShows = (p) => get('/shows/search', { page_size: 100, ...p });
export const getShow = (id) => get(`/shows/${id}`);

// Backend returns one row per screening; the UI needs one card per movie/event.
export function groupByEvent(items) {
  const map = new Map();
  for (const s of items) {
    const g = map.get(s.event.id) || { event: s.event, shows: [], minPrice: null };
    g.shows.push(s);
    if (s.min_price != null) g.minPrice = g.minPrice == null ? +s.min_price : Math.min(g.minPrice, +s.min_price);
    map.set(s.event.id, g);
  }
  return [...map.values()];
}
export const fmtDuration = (m) => (m ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')} min` : '');
export const fmtTime = (iso) => new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: TZ });
export const fmtDate = (iso) => new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: TZ }).replace(/\//g, '.');
export const dayKey = (iso) => new Date(iso).toLocaleDateString('en-CA', { timeZone: TZ });
export const money = (n) => `₹${Number(n).toLocaleString('en-IN')}`;
