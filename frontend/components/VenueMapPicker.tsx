"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

const INDIA_BOUNDS: [[number, number], [number, number]] = [[5.5, 66.5], [38.5, 99]];
const INDIA_CENTRE: [number, number] = [22.8, 79.5];

interface VenueMapPickerProps {
  lat: number | null;
  lng: number | null;
  city?: string;
  onChange: (lat: number | null, lng: number | null) => void;
}

export default function VenueMapPicker({ lat, lng, city, onChange }: VenueMapPickerProps) {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const leafletRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !mapEl.current) return;
      leafletRef.current = L;

      const initialCenter: [number, number] =
        lat != null && lng != null ? [lat, lng] : INDIA_CENTRE;
      const initialZoom = lat != null && lng != null ? 14 : 5;

      const map = L.map(mapEl.current, {
        center: initialCenter,
        zoom: initialZoom,
        minZoom: 4,
        maxBounds: INDIA_BOUNDS,
        maxBoundsViscosity: 0.9,
        zoomControl: true,
      });

      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "© OpenStreetMap contributors",
      }).addTo(map);

      map.on("click", (e: any) => {
        onChange(Number(e.latlng.lat.toFixed(6)), Number(e.latlng.lng.toFixed(6)));
      });

      mapRef.current = map;
      setTimeout(() => map.invalidateSize(), 150);
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      markerRef.current = null;
    };
  }, []);

  // Update marker when lat/lng change
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;

    if (lat != null && lng != null) {
      const at: [number, number] = [lat, lng];
      if (!markerRef.current) {
        const icon = L.divIcon({
          html: '<div style="font-size:28px;line-height:28px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.6))">📍</div>',
          className: "",
          iconSize: [28, 28],
          iconAnchor: [14, 28],
        });
        markerRef.current = L.marker(at, { icon, draggable: true }).addTo(map);
        markerRef.current.on("dragend", () => {
          const pos = markerRef.current.getLatLng();
          onChange(Number(pos.lat.toFixed(6)), Number(pos.lng.toFixed(6)));
        });
      } else {
        markerRef.current.setLatLng(at);
      }
      map.setView(at, Math.max(map.getZoom(), 12));
    } else {
      if (markerRef.current) {
        markerRef.current.remove();
        markerRef.current = null;
      }
    }
  }, [lat, lng, onChange]);

  const useCurrentLocation = () => {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by your browser");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        onChange(
          Number(pos.coords.latitude.toFixed(6)),
          Number(pos.coords.longitude.toFixed(6))
        );
      },
      () => {
        setLocating(false);
        alert("Unable to retrieve your location");
      },
      { timeout: 10000 }
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-slate-400">
          Click on the map or drag the pin to pin the venue location.
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={useCurrentLocation}
            disabled={locating}
            className="rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs text-slate-200 transition hover:bg-slate-700"
          >
            {locating ? "Locating…" : "🎯 Pin Current Location"}
          </button>
          {(lat != null || lng != null) && (
            <button
              type="button"
              onClick={() => onChange(null, null)}
              className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-red-400 transition hover:bg-slate-700"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div
        ref={mapEl}
        className="h-56 w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-800"
      />

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-slate-400">Latitude:</span>{" "}
          <span className="font-mono text-slate-200">{lat != null ? lat.toFixed(6) : "None (approx city)"}</span>
        </div>
        <div>
          <span className="text-slate-400">Longitude:</span>{" "}
          <span className="font-mono text-slate-200">{lng != null ? lng.toFixed(6) : "None (approx city)"}</span>
        </div>
      </div>
    </div>
  );
}
