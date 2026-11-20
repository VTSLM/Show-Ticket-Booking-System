"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { UserLocation } from "@/lib/geo";

const STORAGE_KEY = "ticketflow_location";

interface LocationContextValue {
  location: UserLocation | null;
  ready: boolean; // false until the saved location has been read
  setLocation: (loc: UserLocation) => void;
  clearLocation: () => void;
  pickerOpen: boolean;
  openPicker: () => void;
  closePicker: () => void;
}

const LocationContext = createContext<LocationContextValue | null>(null);

function isValid(v: any): v is UserLocation {
  return (
    v &&
    typeof v.lat === "number" &&
    typeof v.lng === "number" &&
    v.lat >= -90 && v.lat <= 90 &&
    v.lng >= -180 && v.lng <= 180 &&
    typeof v.label === "string"
  );
}

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const [location, setLocationState] = useState<UserLocation | null>(null);
  const [ready, setReady] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (isValid(saved)) setLocationState(saved);
    } catch {}
    setReady(true);
  }, []);

  const setLocation = useCallback((loc: UserLocation) => {
    setLocationState(loc);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(loc));
    } catch {}
  }, []);

  const clearLocation = useCallback(() => {
    setLocationState(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }, []);

  const value = useMemo(
    () => ({
      location,
      ready,
      setLocation,
      clearLocation,
      pickerOpen,
      openPicker: () => setPickerOpen(true),
      closePicker: () => setPickerOpen(false),
    }),
    [location, ready, setLocation, clearLocation, pickerOpen]
  );

  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useLocation(): LocationContextValue {
  const ctx = useContext(LocationContext);
  if (!ctx) throw new Error("useLocation must be used inside <LocationProvider>");
  return ctx;
}
