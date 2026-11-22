// Builds a Google Maps link that opens directions to a venue.

export interface MapsPlace {
  latitude?: number | string | null;
  longitude?: number | string | null;
  venue_name?: string | null;
  address?: string | null;
  city?: string | null;
}

export interface MapsOrigin {
  lat: number;
  lng: number;
}

const isCoord = (v: unknown): boolean =>
  v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));

/**
 * Link that opens Google Maps with the route to the venue.
 * - Uses the venue's pinned position when it has one, else its name + address + city.
 * - When the visitor's location is known it is used as the starting point
 *   (the same point the "km away" badge is measured from).
 * Returns null when there is nothing to point at.
 */
export function googleMapsUrl(place: MapsPlace, from?: MapsOrigin | null): string | null {
  let destination: string;
  if (isCoord(place.latitude) && isCoord(place.longitude)) {
    destination = `${Number(place.latitude)},${Number(place.longitude)}`;
  } else {
    destination = [place.venue_name, place.address, place.city].filter(Boolean).join(", ");
    if (!destination) return null;
  }

  const params = new URLSearchParams({ api: "1", destination });
  if (from && Number.isFinite(from.lat) && Number.isFinite(from.lng)) {
    params.set("origin", `${from.lat},${from.lng}`);
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}
