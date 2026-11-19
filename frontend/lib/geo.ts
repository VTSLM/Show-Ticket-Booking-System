// Small location helpers shared by the navbar, the map picker and the browse page.

export const NEARBY_RADIUS_KM = 100;

export interface IndiaCity {
  name: string;
  state: string;
  lat: number;
  lng: number;
}

export interface UserLocation {
  lat: number;
  lng: number;
  label: string; // shown in the navbar, e.g. "Ahmedabad"
  source: "gps" | "map" | "city";
}

const EARTH_RADIUS_KM = 6371.0088;

// Straight-line distance in km (same formula as the backend)
export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const dPhi = rad(lat2 - lat1);
  const dLmb = rad(lng2 - lng1);
  const a =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLmb / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

// Label for a pin: the city itself when the pin is close to its centre, else "Near <city>"
export function labelForPoint(lat: number, lng: number, cities: IndiaCity[]): string {
  let best: IndiaCity | null = null;
  let bestKm = Infinity;
  for (const c of cities) {
    const d = haversineKm(lat, lng, c.lat, c.lng);
    if (d < bestKm) {
      best = c;
      bestKm = d;
    }
  }
  if (!best) return `${lat.toFixed(2)}, ${lng.toFixed(2)}`;
  return bestKm <= 15 ? best.name : `Near ${best.name}`;
}

// "850 m away", "4.2 km away"; "≈" when the venue has no pinned location yet
export function formatDistance(km: number | null | undefined, exact = true): string | null {
  if (km === null || km === undefined || Number.isNaN(Number(km))) return null;
  const v = Number(km);
  const text = exact && v < 1 ? `${Math.round(v * 1000)} m` : `${v.toFixed(1)} km`;
  return `${exact ? "" : "≈ "}${text} away`;
}
