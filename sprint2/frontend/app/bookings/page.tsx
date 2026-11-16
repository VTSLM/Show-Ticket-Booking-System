"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function BookingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [bookings, setBookings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    if (user) {
      bookingsApi.list().then(setBookings).catch(() => {}).finally(() => setLoading(false));
    }
  }, [user, authLoading]);

  const fmtDate = (ts: string) => {
    try { return new Date(ts).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
    catch { return ts; }
  };
  const fmtTime = (ts: string) => {
    try { return new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }); }
    catch { return ""; }
  };

  const statusConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string }> = {
    confirmed: { label: "Confirmed", color: "#00c977", bg: "#00c97715", border: "#00c97744", glow: "0 0 12px rgba(0,201,119,0.15)" },
    pending:   { label: "Pending",   color: "#ffb300", bg: "#ffb30015", border: "#ffb30044", glow: "0 0 12px rgba(255,179,0,0.15)" },
    cancelled: { label: "Cancelled", color: "#ff4455", bg: "#ff445515", border: "#ff445544", glow: "none" },
  };

  if (loading || authLoading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "var(--background, #090b12)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ textAlign: "center", color: "var(--muted, #9ba3b5)" }}>
          <div
            style={{
              width: 40,
              height: 40,
              border: "3px solid var(--border, #292e3d)",
              borderTopColor: "var(--blue, #287cff)",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
              margin: "0 auto 16px",
            }}
          />
          Loading your bookings…
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--background, #090b12)",
        color: "var(--foreground, #f4f6fb)",
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          background: "linear-gradient(180deg, #0d1120 0%, var(--background, #090b12) 100%)",
          borderBottom: "1px solid var(--border, #292e3d)",
          padding: "40px 24px 28px",
        }}
      >
        <div style={{ maxWidth: 760, margin: "0 auto" }}>
          <p
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              color: "var(--blue, #287cff)",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            Your history
          </p>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <h1 style={{ fontSize: "clamp(1.6rem,4vw,2.4rem)", fontWeight: 800, letterSpacing: "-0.02em", margin: 0 }}>
              My Bookings
            </h1>
            {!loading && bookings.length > 0 && (
              <span
                style={{
                  background: "var(--surface, #11141e)",
                  border: "1px solid var(--border, #292e3d)",
                  borderRadius: 999,
                  padding: "4px 14px",
                  fontSize: 13,
                  color: "var(--muted, #9ba3b5)",
                }}
              >
                {bookings.length} booking{bookings.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px" }}>
        {bookings.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "80px 24px",
              background: "var(--surface, #11141e)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 20,
            }}
          >
            <div style={{ fontSize: 56, marginBottom: 16 }} aria-hidden="true">🎫</div>
            <p style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No bookings yet</p>
            <p style={{ color: "var(--muted, #9ba3b5)", fontSize: 14, marginBottom: 24 }}>
              Your tickets will appear here after you book a show.
            </p>
            <Link
              href="/browse"
              style={{
                display: "inline-block",
                background: "var(--blue, #287cff)",
                color: "#fff",
                textDecoration: "none",
                borderRadius: 10,
                padding: "11px 24px",
                fontSize: 14,
                fontWeight: 700,
              }}
            >
              Browse Shows
            </Link>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {bookings.map((b) => {
              const sc = statusConfig[b.status] ?? statusConfig.pending;
              return (
                <Link
                  key={b.id}
                  href={`/bookings/${b.id}`}
                  style={{ textDecoration: "none", display: "block" }}
                  className="booking-card"
                >
                  <div
                    className="booking-card-inner"
                    style={{
                      background: "var(--surface, #11141e)",
                      border: "1px solid var(--border, #292e3d)",
                      borderRadius: 16,
                      padding: "18px 20px",
                      display: "flex",
                      gap: 16,
                      alignItems: "flex-start",
                      transition: "transform 0.18s, border-color 0.18s, box-shadow 0.18s",
                    }}
                  >
                    {/* Left accent bar */}
                    <div
                      style={{
                        width: 4,
                        minHeight: 56,
                        borderRadius: 4,
                        background: sc.color,
                        flexShrink: 0,
                        alignSelf: "stretch",
                        opacity: 0.7,
                      }}
                    />

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <div>
                          <h3
                            style={{
                              fontSize: 16,
                              fontWeight: 700,
                              color: "var(--foreground, #f4f6fb)",
                              margin: "0 0 3px",
                            }}
                            className="booking-title"
                          >
                            {b.event_title || "Booking"}
                          </h3>
                          <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: "0 0 2px" }}>
                            📍 {b.venue_name}{b.city ? `, ${b.city}` : ""}
                          </p>
                          <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: 0 }}>
                            🕐 {fmtDate(b.start_time)} · {fmtTime(b.start_time)}
                          </p>
                        </div>

                        {/* Status pill */}
                        <span
                          style={{
                            display: "inline-block",
                            padding: "4px 12px",
                            borderRadius: 999,
                            fontSize: 11,
                            fontWeight: 700,
                            letterSpacing: "0.07em",
                            textTransform: "uppercase",
                            background: sc.bg,
                            color: sc.color,
                            border: `1px solid ${sc.border}`,
                            boxShadow: sc.glow,
                            flexShrink: 0,
                          }}
                        >
                          {sc.label}
                        </span>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginTop: 14,
                          paddingTop: 12,
                          borderTop: "1px solid var(--border, #292e3d)",
                          flexWrap: "wrap",
                          gap: 10,
                        }}
                      >
                        <span style={{ fontSize: 13, color: "var(--muted, #9ba3b5)" }}>
                          🎟 {b.seat_count ?? "—"} seat{b.seat_count !== 1 ? "s" : ""}
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <span
                            style={{
                              fontSize: 18,
                              fontWeight: 800,
                              color: "var(--blue, #287cff)",
                              letterSpacing: "-0.01em",
                            }}
                          >
                            ₹{parseFloat(b.total_amount).toFixed(2)}
                          </span>
                          {b.status === "pending" && (
                            <Link
                              href={`/payment?booking_id=${b.id}`}
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                background: "#ffb30015",
                                border: "1px solid #ffb30050",
                                color: "#ffb300",
                                textDecoration: "none",
                                borderRadius: 8,
                                padding: "5px 14px",
                                fontSize: 12,
                                fontWeight: 700,
                              }}
                            >
                              Pay Now
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .booking-card:hover .booking-card-inner {
          transform: translateY(-2px);
          border-color: rgba(40,124,255,0.4) !important;
          box-shadow: 0 8px 32px rgba(40,124,255,0.08);
        }
        .booking-card:hover .booking-title {
          color: var(--blue, #287cff) !important;
        }
      `}</style>
    </div>
  );
}
