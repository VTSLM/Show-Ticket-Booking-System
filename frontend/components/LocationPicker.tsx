"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";
import { useLocation } from "@/contexts/LocationContext";
import { NEARBY_RADIUS_KM, IndiaCity, UserLocation, labelForPoint } from "@/lib/geo";

// Rough box around India, used to keep the map on India and to reject GPS fixes abroad
const INDIA_BOUNDS: [[number, number], [number, number]] = [[5.5, 66.5], [38.5, 99]];
const INDIA_CENTRE: [number, number] = [22.8, 79.5];

interface Pin {
  lat: number;
  lng: number;
  label?: string; // set when a city was picked from the list
  source: UserLocation["source"];
}

const insideIndia = (lat: number, lng: number) =>
  lat >= INDIA_BOUNDS[0][0] && lat <= INDIA_BOUNDS[1][0] && lng >= INDIA_BOUNDS[0][1] && lng <= INDIA_BOUNDS[1][1];

export default function LocationPicker() {
  const { location, pickerOpen, closePicker, setLocation, clearLocation } = useLocation();

  const [cities, setCities] = useState<IndiaCity[]>([]);
  const [query, setQuery] = useState("");
  const [pin, setPin] = useState<Pin | null>(null);
  const [locating, setLocating] = useState(false);

  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const leafletRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const circleRef = useRef<any>(null);

  // Start from the saved location each time the picker opens
  useEffect(() => {
    if (!pickerOpen) return;
    setQuery("");
    setPin(location ? { lat: location.lat, lng: location.lng, label: location.label, source: location.source } : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickerOpen]);

  useEffect(() => {
    if (pickerOpen && cities.length === 0) {
      browseApi.indiaCities().then(setCities).catch(() => {});
    }
  }, [pickerOpen, cities.length]);

  useEffect(() => {
    if (!pickerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closePicker();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pickerOpen, closePicker]);

  // Build the map when the picker opens, tear it down when it closes
  useEffect(() => {
    if (!pickerOpen) return;
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !mapEl.current) return;
      leafletRef.current = L;

      const map = L.map(mapEl.current, {
        center: INDIA_CENTRE,
        zoom: 5,
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
        setPin({ lat: e.latlng.lat, lng: e.latlng.lng, source: "map" });
      });
      mapRef.current = map;
      setTimeout(() => map.invalidateSize(), 150);
      // draw the starting pin (the effect below only runs when the pin changes)
      setPin((p) => (p ? { ...p } : p));
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      markerRef.current = null;
      circleRef.current = null;
    };
  }, [pickerOpen]);

  // Keep the marker and the 100 km circle in step with the pin
  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!map || !L || !pin) return;
    const at: [number, number] = [pin.lat, pin.lng];

    if (!markerRef.current) {
      const icon = L.divIcon({
        html: '<div style="font-size:30px;line-height:30px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.6))">📍</div>',
        className: "",
        iconSize: [30, 30],
        iconAnchor: [15, 30],
      });
      markerRef.current = L.marker(at, { icon, draggable: true }).addTo(map);
      markerRef.current.on("dragend", () => {
        const p = markerRef.current.getLatLng();
        setPin({ lat: p.lat, lng: p.lng, source: "map" });
      });
    } else {
      markerRef.current.setLatLng(at);
    }

    if (!circleRef.current) {
      circleRef.current = L.circle(at, {
        radius: NEARBY_RADIUS_KM * 1000,
        color: "#287cff",
        weight: 2,
        fillColor: "#287cff",
        fillOpacity: 0.12,
      }).addTo(map);
    } else {
      circleRef.current.setLatLng(at);
    }
    map.fitBounds(circleRef.current.getBounds(), { padding: [20, 20], animate: true });
  }, [pin]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return cities
      .filter((c) => c.name.toLowerCase().includes(q) || c.state.toLowerCase().includes(q))
      .slice(0, 8);
  }, [query, cities]);

  const pickCity = (c: IndiaCity) => {
    setPin({ lat: c.lat, lng: c.lng, label: c.name, source: "city" });
    setQuery("");
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      toast.error("Your browser can't share its location. Pick a city instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const { latitude, longitude } = pos.coords;
        if (!insideIndia(latitude, longitude)) {
          toast.error("Your location is outside India. Pick a city on the map.");
          return;
        }
        setPin({ lat: latitude, lng: longitude, source: "gps" });
      },
      (err) => {
        setLocating(false);
        toast.error(
          err.code === err.PERMISSION_DENIED
            ? "Location permission was denied. Pick a city instead."
            : "Couldn't get your location. Pick a city instead."
        );
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  };

  const confirm = () => {
    if (!pin) return;
    setLocation({
      lat: pin.lat,
      lng: pin.lng,
      label: pin.label ?? labelForPoint(pin.lat, pin.lng, cities),
      source: pin.source,
    });
    closePicker();
  };

  if (!pickerOpen) return null;

  const pinLabel = pin ? pin.label ?? labelForPoint(pin.lat, pin.lng, cities) : null;

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/75 p-3 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && closePicker()}
      role="dialog"
      aria-modal="true"
      aria-label="Choose your location"
    >
      <div className="flex max-h-[94vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-800 p-4">
          <div>
            <h2 className="text-lg font-bold text-white">Where are you?</h2>
            <p className="text-xs text-slate-400">
              Shows are listed within {NEARBY_RADIUS_KM} km of this spot. Concerts are shown from everywhere.
            </p>
          </div>
          <button
            type="button"
            onClick={closePicker}
            aria-label="Close"
            className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 p-4 pb-2">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <input
                className="input w-full"
                placeholder="Search your city (e.g. Ahmedabad)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search city"
              />
              {matches.length > 0 && (
                <ul className="absolute left-0 right-0 top-full z-[1100] mt-1 max-h-56 overflow-auto rounded-xl border border-slate-700 bg-slate-900 shadow-xl">
                  {matches.map((c) => (
                    <li key={c.name}>
                      <button
                        type="button"
                        onClick={() => pickCity(c)}
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-white hover:bg-slate-800"
                      >
                        <span>{c.name}</span>
                        <span className="text-xs text-slate-400">{c.state}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button
              type="button"
              onClick={useMyLocation}
              disabled={locating}
              className="btn-secondary whitespace-nowrap"
            >
              {locating ? "Locating…" : "🎯 Use my current location"}
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Or tap anywhere on the map, then drag the pin to fine-tune it.
          </p>
        </div>

        <div className="px-4">
          <div
            ref={mapEl}
            className="h-[320px] w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-800 sm:h-[360px]"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="min-w-0 text-sm">
            {pin ? (
              <>
                <p className="truncate font-semibold text-white">📍 {pinLabel}</p>
                <p className="text-xs text-slate-400">
                  {pin.lat.toFixed(4)}, {pin.lng.toFixed(4)}
                </p>
              </>
            ) : (
              <p className="text-slate-400">No location chosen yet</p>
            )}
          </div>
          <div className="flex gap-2">
            {location && (
              <button
                type="button"
                onClick={() => {
                  clearLocation();
                  closePicker();
                }}
                className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-red-500/60 hover:text-red-400"
              >
                Remove
              </button>
            )}
            <button
              type="button"
              onClick={confirm}
              disabled={!pin}
              className="btn-primary disabled:opacity-40"
            >
              Show shows within {NEARBY_RADIUS_KM} km
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
