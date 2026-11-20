"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { browseApi, seatsApi, bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import VenueLayoutCanvas, { SeatItem, ZoneItem } from "@/components/VenueLayoutCanvas";
import TermsAndConditionsModal from "@/components/TermsAndConditionsModal";

export default function SeatsPage() {
  const { showId } = useParams<{ showId: string }>();
  const router = useRouter();
  const { user, profile, loading: authLoading } = useAuth();

  const [show, setShow] = useState<any>(null);
  const [seats, setSeats] = useState<SeatItem[]>([]);
  const [zones, setZones] = useState<ZoneItem[]>([]);
  const [layoutType, setLayoutType] = useState<string>("cinema");
  const [stagePosition, setStagePosition] = useState<string>("front");
  const [layoutConfig, setLayoutConfig] = useState<any>(null);

  // Terms and conditions state
  const [termsText, setTermsText] = useState<string>("");
  const [termsHash, setTermsHash] = useState<string>("");
  const [isDefaultTerms, setIsDefaultTerms] = useState<boolean>(true);
  const [isTermsModalOpen, setIsTermsModalOpen] = useState<boolean>(false);

  // Selection state
  const [selectedSeatIds, setSelectedSeatIds] = useState<string[]>([]);
  const [selectedZone, setSelectedZone] = useState<ZoneItem | null>(null);
  const [selectedZoneQty, setSelectedZoneQty] = useState<number>(1);

  // Hold timer countdown (10 minutes = 600s)
  const [holdSecondsLeft, setHoldSecondsLeft] = useState<number>(600);
  const [loading, setLoading] = useState<boolean>(true);
  const [isBooking, setIsBooking] = useState<boolean>(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load seat map and layout metadata
  const loadSeats = useCallback(async () => {
    try {
      const data = await seatsApi.map(showId);
      const seatList: any[] = Array.isArray(data) ? data : (data?.seats || []);
      const zoneList: any[] = Array.isArray(data?.zones) ? data.zones : [];

      if (data?.layout_type) setLayoutType(data.layout_type);
      if (data?.stage_position) setStagePosition(data.stage_position);
      if (data?.layout_config) setLayoutConfig(data.layout_config);
      if (data?.terms_and_conditions) setTermsText(data.terms_and_conditions);
      if (data?.terms_hash) setTermsHash(data.terms_hash);
      if (data?.is_default_terms !== undefined) setIsDefaultTerms(data.is_default_terms);

      setZones(zoneList);
      setSeats(
        seatList.map((seat: any) => ({
          ...seat,
          status:
            seat.status === "locked" && seat.locked_by === profile?.id
              ? "mine"
              : seat.status,
        }))
      );
    } catch {
      toast.error("Failed to load seats");
    }
  }, [showId, profile?.id]);

  // Initial data loading and WebSocket updates
  useEffect(() => {
    let isMounted = true;

    browseApi
      .showDetail(showId)
      .then((data) => {
        if (isMounted) setShow(data);
      })
      .catch(() => {
        if (isMounted) toast.error("Failed to load show details");
      });

    loadSeats().finally(() => {
      if (isMounted) setLoading(false);
    });

    let socket: WebSocket | undefined;
    try {
      const wsUrl = `${apiUrl.replace(/^http/, "ws")}/api/seats/${showId}/ws`;
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          // Instant local state update from WebSocket events without full network refetch
          if (message.type === "lock" && Array.isArray(message.seat_ids)) {
            setSeats((prev) =>
              prev.map((s) =>
                message.seat_ids.includes(s.show_seat_id)
                  ? {
                      ...s,
                      status:
                        selectedSeatIds.includes(s.show_seat_id) ||
                        (profile?.id && message.user_id === profile.id)
                          ? "mine"
                          : "locked",
                    }
                  : s
              )
            );
          } else if (message.type === "release" && Array.isArray(message.seat_ids)) {
            setSeats((prev) =>
              prev.map((s) =>
                message.seat_ids.includes(s.show_seat_id)
                  ? { ...s, status: "available" }
                  : s
              )
            );
          } else if (message.type === "zone_update" && message.zone_id) {
            setZones((prev) =>
              prev.map((z) =>
                z.id === message.zone_id
                  ? { ...z, available_capacity: message.available_capacity }
                  : z
              )
            );
          }
        } catch {}
      };
    } catch {}

    return () => {
      isMounted = false;
      socket?.close();
    };
  }, [showId, apiUrl, loadSeats, profile?.id]);

  // Hold Timer Effect
  useEffect(() => {
    // Only signed-in users get a real hold on the server, so only they see a countdown.
    if (user && (selectedSeatIds.length > 0 || selectedZone)) {
      if (!timerRef.current) {
        setHoldSecondsLeft(600); // 10 minutes
        timerRef.current = setInterval(() => {
          setHoldSecondsLeft((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              timerRef.current = null;
              toast.error("Hold expired. Seats have been released.");
              setSelectedSeatIds([]);
              setSelectedZone(null);
              loadSeats();
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      }
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setHoldSecondsLeft(600);
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [user, selectedSeatIds.length, selectedZone, loadSeats]);

  // Seat toggle handler: immediate selection with zero flickering or buffering
  const handleToggleSeat = async (seat: SeatItem) => {
    if (seat.status === "booked" || seat.status === "locked" || seat.status === "reserved") {
      return;
    }

    const seatId = seat.show_seat_id;
    const isCurrentlySelected = selectedSeatIds.includes(seatId);

    // 1. DESELECT SEAT
    if (isCurrentlySelected) {
      setSelectedSeatIds((prev) => prev.filter((id) => id !== seatId));
      setSeats((prev) =>
        prev.map((s) => (s.show_seat_id === seatId ? { ...s, status: "available" } : s))
      );

      if (user) {
        seatsApi.release(showId, [seatId]).catch(() => {});
      }
      return;
    }

    // Clear zone pass if switching to numbered seats
    if (selectedZone) {
      setSelectedZone(null);
    }

    // Limit maximum seats per booking
    if (selectedSeatIds.length >= 10) {
      toast.error("Maximum 10 tickets allowed per transaction");
      return;
    }

    // 2. SELECT SEAT
    setSelectedSeatIds((prev) => [...prev, seatId]);
    setSeats((prev) =>
      prev.map((s) => (s.show_seat_id === seatId ? { ...s, status: "mine" } : s))
    );

    // If user is authenticated, lock on backend
    if (user) {
      try {
        await seatsApi.lock(showId, [seatId]);
      } catch (err: any) {
        if (err.message && (err.message.includes("409") || err.message.includes("already locked"))) {
          setSelectedSeatIds((prev) => prev.filter((id) => id !== seatId));
          setSeats((prev) =>
            prev.map((s) => (s.show_seat_id === seatId ? { ...s, status: "locked" } : s))
          );
          toast.error("Seat was just taken by another user");
        }
      }
    }
  };

  // Zone selection handler (Concerts, Standing, Passes)
  const handleSelectZone = (zone: ZoneItem) => {
    if (authLoading) return;
    if (!user) {
      toast.error("Please log in to select passes");
      router.push(`/auth/login?redirect=/shows/${showId}/seats`);
      return;
    }

    // Deselect numbered seats if switching to standing zone
    if (selectedSeatIds.length > 0) {
      seatsApi.release(showId, selectedSeatIds).catch(() => {});
      setSeats((prev) =>
        prev.map((s) =>
          selectedSeatIds.includes(s.show_seat_id) ? { ...s, status: "available" } : s
        )
      );
      setSelectedSeatIds([]);
    }

    if (selectedZone?.id === zone.id) {
      setSelectedZone(null);
    } else {
      setSelectedZone(zone);
      setSelectedZoneQty(1);
      toast.success(`Selected ${zone.name}`);
    }
  };

  // Step 1: User clicks "Proceed to Payment" -> Check Auth and Open Terms & Conditions Modal
  const handleInitiatePayment = () => {
    if (!selectedSeatIds.length && !selectedZone) {
      toast.error("Select seats or a ticket zone to proceed");
      return;
    }
    if (!user) {
      toast.error("Please log in to proceed to payment");
      router.push(`/auth/login?redirect=/shows/${showId}/seats`);
      return;
    }
    // Open Show-Specific Terms & Conditions Modal
    setIsTermsModalOpen(true);
  };

  // Step 2: User explicitly accepts T&C inside Modal -> Record Acceptance & Proceed
  const handleAcceptTermsAndProceed = async (acceptedHash: string, acceptedText: string) => {
    setIsBooking(true);
    try {
      let result: any;
      if (selectedZone) {
        result = await bookingsApi.create({
          show_id: showId,
          zone_id: selectedZone.id,
          zone_quantity: selectedZoneQty,
          terms_accepted: true,
          terms_hash: acceptedHash,
          terms_text: acceptedText,
        });
      } else {
        result = await bookingsApi.create({
          show_id: showId,
          seat_ids: selectedSeatIds,
          terms_accepted: true,
          terms_hash: acceptedHash,
          terms_text: acceptedText,
        });
      }

      // Explicitly record customer acceptance in backend
      try {
        await bookingsApi.acceptTerms(result.booking_id, {
          terms_hash: acceptedHash,
          terms_text: acceptedText,
        });
      } catch {}

      toast.success("Terms accepted. Proceeding to checkout...");
      setIsTermsModalOpen(false);
      router.push(`/payment?booking_id=${result.booking_id}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to create booking");
    } finally {
      setIsBooking(false);
    }
  };

  // Calculations for persistent summary
  const seatsTotal = seats
    .filter((s) => selectedSeatIds.includes(s.show_seat_id))
    .reduce((sum, s) => sum + Number(s.price || 0), 0);

  const grandTotal = selectedZone
    ? Number(selectedZone.price || 0) * selectedZoneQty
    : seatsTotal;

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090b12] text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          <p className="text-sm font-medium">Loading flexible venue layout…</p>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#090b12] text-[#f4f6fb] pb-32">
      {/* 1. Header Breadcrumbs & Show Summary Banner */}
      {show && (
        <div className="border-b border-slate-800 bg-[#0d101a] px-4 py-5 sm:px-8">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {show.poster_url && (
                <img
                  src={show.poster_url}
                  alt={show.title}
                  className="h-16 w-12 sm:h-20 sm:w-14 shrink-0 rounded-lg border border-slate-700 object-cover shadow-md"
                />
              )}
              <div>
                <div className="flex items-center gap-2 text-xs text-blue-400 font-bold uppercase tracking-wider">
                  <Link href={`/shows/${showId}`} className="hover:underline">
                    ← Show Details
                  </Link>
                  <span>•</span>
                  <span>Interactive Venue Layout</span>
                </div>
                <h1 className="mt-1 text-xl font-extrabold text-white sm:text-2xl">
                  {show.title}
                </h1>
                <p className="mt-0.5 text-xs text-slate-300">
                  📍 {show.venue_name}{show.screen_name ? ` — ${show.screen_name}` : ""}
                  {show.start_time && (
                    <span className="text-slate-400">
                      {" "}
                      • 🗓{" "}
                      {new Date(show.start_time).toLocaleString("en-IN", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Hold countdown timer badge (visible if items are selected) */}
            {user && (selectedSeatIds.length > 0 || selectedZone) && (
              <div
                className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-mono font-bold shadow-sm ${
                  holdSecondsLeft < 120
                    ? "border-red-500/50 bg-red-950/40 text-red-400 animate-pulse"
                    : "border-blue-500/40 bg-blue-950/30 text-blue-300"
                }`}
              >
                <span>⏱ Hold Timer:</span>
                <span className="text-sm font-extrabold">{formatTimer(holdSecondsLeft)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. Generalized Interactive Venue Canvas */}
      <div className="mx-auto max-w-7xl px-3 py-6 sm:px-6 lg:px-8">
        <VenueLayoutCanvas
          layoutType={layoutType}
          stagePosition={stagePosition}
          layoutConfig={layoutConfig}
          seats={seats}
          zones={zones}
          selectedSeatIds={selectedSeatIds}
          selectedZoneId={selectedZone?.id}
          onToggleSeat={handleToggleSeat}
          onSelectZone={handleSelectZone}
        />
      </div>

      {/* 3. Persistent Sticky Booking Summary & Checkout Action */}
      {(selectedSeatIds.length > 0 || selectedZone) && (
        <div className="fixed bottom-6 left-1/2 z-40 flex w-[94%] max-w-2xl -translate-x-1/2 items-center justify-between rounded-2xl border border-slate-700/80 bg-slate-900/95 p-4 shadow-2xl shadow-black/90 backdrop-blur-md">
          <div>
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <span className="font-semibold text-white">
                {selectedZone
                  ? `${selectedZoneQty} × ${selectedZone.name}`
                  : `${selectedSeatIds.length} seat${selectedSeatIds.length > 1 ? "s" : ""} selected`}
              </span>
              <span>•</span>
              {user ? (
                <span className="font-mono text-amber-400">Hold: {formatTimer(holdSecondsLeft)}</span>
              ) : (
                <span className="text-amber-300" data-testid="guest-hold-note">Log in to hold these seats</span>
              )}
            </div>
            <p className="mt-0.5 text-xl font-extrabold text-blue-400">
              ₹{grandTotal.toLocaleString("en-IN")}
            </p>
          </div>

          {/* If zone selected, show quantity increment/decrement */}
          {selectedZone && (
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-xs">
              <span className="text-slate-400">Qty:</span>
              <button
                type="button"
                onClick={() => setSelectedZoneQty((q) => Math.max(1, q - 1))}
                className="h-6 w-6 rounded bg-slate-700 font-bold text-white hover:bg-slate-600 transition active:scale-95"
              >
                −
              </button>
              <span className="w-5 text-center font-bold text-white">{selectedZoneQty}</span>
              <button
                type="button"
                onClick={() =>
                  setSelectedZoneQty((q) => Math.min(Math.min(selectedZone.available_capacity, 10), q + 1))
                }
                className="h-6 w-6 rounded bg-slate-700 font-bold text-white hover:bg-slate-600 transition active:scale-95"
              >
                +
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleInitiatePayment}
            className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/30 transition hover:bg-blue-500 active:scale-95"
          >
            Proceed to Payment →
          </button>
        </div>
      )}

      {/* 4. Show-Specific Terms & Conditions Modal */}
      <TermsAndConditionsModal
        isOpen={isTermsModalOpen}
        eventTitle={show?.title || "Event"}
        venueName={show?.venue_name || "Venue"}
        showTime={
          show?.start_time
            ? new Date(show.start_time).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
              })
            : undefined
        }
        termsText={termsText}
        termsHash={termsHash}
        isDefaultTerms={isDefaultTerms}
        holdSecondsLeft={holdSecondsLeft}
        isSubmitting={isBooking}
        onAccept={handleAcceptTermsAndProceed}
        onCancel={() => setIsTermsModalOpen(false)}
      />
    </main>
  );
}
