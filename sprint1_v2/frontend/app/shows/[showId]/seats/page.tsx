"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { browseApi, seatsApi, bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import clsx from "clsx";

type SeatStatus = "available" | "locked" | "booked" | "reserved" | "mine";

interface Seat {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: string;
  status: SeatStatus;
  price: number;
  locked_by?: string;
}

export default function SeatsPage() {
  const { showId } = useParams<{ showId: string }>();
  const router = useRouter();
  const { user, profile } = useAuth();

  const [show, setShow] = useState<any>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const loadSeats = useCallback(async () => {
    try {
      const data = await seatsApi.map(showId);
      setSeats(
        data.map((seat: any) => ({
          ...seat,
          status:
            seat.status === "locked" && seat.locked_by === profile?.id
              ? "mine"
              : seat.status,
        })),
      );
    } catch {
      toast.error("Failed to load seats");
    }
  }, [showId, profile?.id]);

  useEffect(() => {
    let isMounted = true;

    browseApi.showDetail(showId)
      .then((data) => { if (isMounted) setShow(data); })
      .catch(() => { if (isMounted) toast.error("Failed to load show details"); });

    loadSeats().finally(() => { if (isMounted) setLoading(false); });

    let socket: WebSocket | undefined;
    try {
      const wsUrl = `${apiUrl.replace(/^http/, "ws")}/api/seats/${showId}/ws`;
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "lock" || message.type === "release") loadSeats();
        } catch {}
      };
    } catch {}

    return () => {
      isMounted = false;
      socket?.close();
    };
  }, [showId, apiUrl, loadSeats]);

  const toggle = async (seat: Seat) => {
    if (!user) {
      toast.error("Please log in first");
      router.push("/auth/login");
      return;
    }
    if (seat.status === "booked" || seat.status === "locked" || seat.status === "reserved") return;

    const seatId = seat.show_seat_id;
    if (selected.includes(seatId)) {
      setSelected((current) => current.filter((id) => id !== seatId));
      try { await seatsApi.release(showId, [seatId]); await loadSeats(); }
      catch { toast.error("Could not release this seat"); }
      return;
    }
    try {
      await seatsApi.lock(showId, [seatId]);
      setSelected((current) => [...current, seatId]);
      await loadSeats();
    } catch (error: any) {
      toast.error(error.message || "Seat is no longer available");
      await loadSeats();
    }
  };

  const handleBook = async () => {
    if (!selected.length) { toast.error("Select at least one seat"); return; }
    setBooking(true);
    try {
      const result = (await bookingsApi.create(showId, selected)) as { booking_id: string };
      toast.success("Booking created! Proceeding to payment...");
      router.push(`/payment?booking_id=${result.booking_id}`);
    } catch (error: any) {
      toast.error(error.message || "Booking failed");
    } finally {
      setBooking(false);
    }
  };

  const rows = seats.reduce<Record<string, Seat[]>>((result, seat) => {
    if (!result[seat.row_label]) result[seat.row_label] = [];
    result[seat.row_label].push(seat);
    return result;
  }, {});

  /* Seat colour — dark-theme friendly */
  const seatStyle = (seat: Seat): React.CSSProperties => {
    const base: React.CSSProperties = {
      width: 34,
      height: 34,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "6px 6px 4px 4px",
      border: "1.5px solid",
      fontSize: 10,
      fontWeight: 700,
      cursor: "pointer",
      transition: "transform 0.1s, opacity 0.1s",
      flexShrink: 0,
    };
    if (selected.includes(seat.show_seat_id))
      return { ...base, background: "#287cff", borderColor: "#5aa0ff", color: "#fff", boxShadow: "0 0 10px rgba(40,124,255,0.5)" };
    if (seat.status === "booked")
      return { ...base, background: "#1e2230", borderColor: "#363c50", color: "#555e78", cursor: "not-allowed" };
    if (seat.status === "locked")
      return { ...base, background: "#2a1f00", borderColor: "#5a4200", color: "#7a5e00", cursor: "not-allowed" };
    if (seat.status === "reserved")
      return { ...base, background: "#1e2230", borderColor: "#363c50", color: "#555e78", cursor: "not-allowed" };
    if (seat.status === "mine")
      return { ...base, background: "#1a3060", borderColor: "#2a4a90", color: "#6090e0" };
    const t = seat.seat_type?.toLowerCase();
    if (t === "premium" || t === "vip" || t === "recliner")
      return { ...base, background: "#2a1f00", borderColor: "#a07820", color: "#d4a832" };
    return { ...base, background: "#0a2a1a", borderColor: "#0d6b34", color: "#2ae87c" };
  };

  const total = seats
    .filter((seat) => selected.includes(seat.show_seat_id))
    .reduce((sum, seat) => sum + Number(seat.price || 0), 0);

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "var(--background, #090b12)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 16,
          color: "var(--muted, #9ba3b5)",
        }}
      >
        <div
          style={{
            width: 40, height: 40,
            border: "3px solid var(--border, #292e3d)",
            borderTopColor: "var(--blue, #287cff)",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
        Loading seat map…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "var(--background, #090b12)",
        color: "var(--foreground, #f4f6fb)",
        paddingBottom: 100,
      }}
    >
      {/* ── Show info banner ── */}
      {show && (
        <div
          style={{
            background: "linear-gradient(180deg, #0d1120 0%, var(--background,#090b12) 100%)",
            borderBottom: "1px solid var(--border, #292e3d)",
            padding: "32px 24px 24px",
          }}
        >
          <div style={{ maxWidth: 900, margin: "0 auto", display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
            {show.poster_url && (
              <img
                src={show.poster_url}
                alt="poster"
                style={{ width: 60, height: 90, objectFit: "cover", borderRadius: 8, flexShrink: 0, border: "1px solid var(--border,#292e3d)" }}
              />
            )}
            <div>
              <p
                style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: "0.18em",
                  color: "var(--blue, #287cff)", textTransform: "uppercase", marginBottom: 6,
                }}
              >
                Choose your seats
              </p>
              <h1 style={{ fontSize: "clamp(1.4rem,3vw,2rem)", fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 6px" }}>
                {show.title || show.event_title}
              </h1>
              <p style={{ fontSize: 14, color: "#c8d0e0", margin: "0 0 3px" }}>
                📍 {show.venue_name}{show.screen_name ? ` — ${show.screen_name}` : ""}
              </p>
              {show.start_time && (
                <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: 0 }}>
                  🕐 {new Date(show.start_time).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "28px 24px" }}>
        {/* ── Seat map ── */}
        <div
          style={{
            background: "var(--surface, #11141e)",
            border: "1px solid var(--border, #292e3d)",
            borderRadius: 20,
            padding: "28px 20px",
          }}
        >
          {/* Screen arc */}
          <div style={{ textAlign: "center", marginBottom: 36 }}>
            <div
              style={{
                display: "inline-block",
                background: "linear-gradient(180deg, rgba(40,124,255,0.18) 0%, transparent 100%)",
                border: "2px solid rgba(40,124,255,0.35)",
                borderBottom: "none",
                borderRadius: "80px 80px 0 0",
                padding: "10px 60px 0",
                marginBottom: 4,
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: "0.3em",
                  color: "rgba(40,124,255,0.7)",
                  textTransform: "uppercase",
                }}
              >
                SCREEN
              </span>
            </div>
            <div
              style={{
                height: 2,
                background: "linear-gradient(90deg, transparent, rgba(40,124,255,0.4), transparent)",
                marginBottom: 8,
              }}
            />
            <p style={{ fontSize: 11, color: "var(--muted,#9ba3b5)", margin: 0 }}>All eyes this way</p>
          </div>

          {/* Seat grid */}
          <div style={{ overflowX: "auto", paddingBottom: 8 }}>
            <div style={{ minWidth: "max-content", margin: "0 auto", width: "max-content" }}>
              {Object.keys(rows).length === 0 ? (
                <p style={{ textAlign: "center", color: "var(--muted,#9ba3b5)", padding: "40px 0" }}>
                  No seats available for this show.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {Object.entries(rows)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([row, rowSeats]) => (
                      <div key={row} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            width: 24, textAlign: "center", fontSize: 11,
                            fontWeight: 700, color: "var(--muted,#9ba3b5)", flexShrink: 0,
                          }}
                        >
                          {row}
                        </span>
                        <div style={{ display: "flex", gap: 6 }}>
                          {[...rowSeats]
                            .sort((a, b) => a.seat_number - b.seat_number)
                            .map((seat) => (
                              <button
                                key={seat.show_seat_id}
                                type="button"
                                onClick={() => toggle(seat)}
                                title={`${seat.row_label}${seat.seat_number} — ₹${seat.price} (${seat.seat_type})`}
                                aria-label={`Row ${seat.row_label}, seat ${seat.seat_number}, ₹${seat.price}`}
                                aria-pressed={selected.includes(seat.show_seat_id)}
                                disabled={seat.status === "booked" || seat.status === "locked" || seat.status === "reserved"}
                                style={seatStyle(seat)}
                                onMouseEnter={(e) => {
                                  if (!["booked","locked","reserved"].includes(seat.status))
                                    (e.currentTarget as HTMLElement).style.transform = "scale(1.15)";
                                }}
                                onMouseLeave={(e) => {
                                  (e.currentTarget as HTMLElement).style.transform = "scale(1)";
                                }}
                              >
                                {seat.seat_number}
                              </button>
                            ))}
                        </div>
                        <span
                          style={{
                            width: 24, textAlign: "center", fontSize: 11,
                            fontWeight: 700, color: "var(--muted,#9ba3b5)", flexShrink: 0,
                          }}
                        >
                          {row}
                        </span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>

          {/* Legend */}
          <div
            style={{
              marginTop: 28,
              paddingTop: 20,
              borderTop: "1px solid var(--border, #292e3d)",
              display: "flex",
              flexWrap: "wrap",
              gap: "8px 20px",
              justifyContent: "center",
            }}
          >
            {[
              { bg: "#0a2a1a", border: "#0d6b34", color: "#2ae87c", label: "Available" },
              { bg: "#287cff", border: "#5aa0ff", color: "#fff", label: "Selected" },
              { bg: "#2a1f00", border: "#a07820", color: "#d4a832", label: "Premium" },
              { bg: "#2a1f00", border: "#5a4200", color: "#7a5e00", label: "Locked" },
              { bg: "#1e2230", border: "#363c50", color: "#555e78", label: "Booked" },
            ].map(({ bg, border, color, label }) => (
              <span
                key={label}
                style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: "var(--muted,#9ba3b5)" }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 16, height: 16, borderRadius: "4px 4px 3px 3px",
                    background: bg, border: `1.5px solid ${border}`, flexShrink: 0,
                  }}
                />
                {label}
              </span>
            ))}
          </div>
        </div>

        {/* ── Sticky booking bar ── */}
        {selected.length > 0 && (
          <div
            style={{
              position: "fixed",
              bottom: 24,
              left: "50%",
              transform: "translateX(-50%)",
              background: "var(--surface-raised, #181c28)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 16,
              padding: "16px 24px",
              display: "flex",
              alignItems: "center",
              gap: 24,
              boxShadow: "0 8px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(40,124,255,0.1)",
              backdropFilter: "blur(12px)",
              zIndex: 100,
              minWidth: 300,
              maxWidth: "calc(100vw - 48px)",
            }}
          >
            <div>
              <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: "0 0 2px" }}>
                {selected.length} seat{selected.length !== 1 ? "s" : ""} selected
              </p>
              <p style={{ fontSize: 20, fontWeight: 800, color: "var(--blue, #287cff)", letterSpacing: "-0.02em", margin: 0 }}>
                ₹{total.toLocaleString("en-IN")}
              </p>
            </div>
            <button
              type="button"
              onClick={handleBook}
              disabled={booking}
              style={{
                marginLeft: "auto",
                background: booking ? "var(--surface,#11141e)" : "var(--blue, #287cff)",
                color: booking ? "var(--muted,#9ba3b5)" : "#fff",
                border: "none",
                borderRadius: 10,
                padding: "12px 24px",
                fontSize: 14,
                fontWeight: 700,
                cursor: booking ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
                transition: "background 0.15s",
              }}
            >
              {booking ? "Processing…" : "Proceed to Payment →"}
            </button>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}
