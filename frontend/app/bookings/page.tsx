"use client";
import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

type FilterTab = "all" | "upcoming" | "completed" | "cancelled" | "refund_pending" | "refunded";

export default function BookingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [bookings, setBookings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
      return;
    }
    if (user) {
      bookingsApi
        .list()
        .then(setBookings)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [user, authLoading, router]);

  const fmtDate = (ts: string) => {
    try {
      return new Date(ts).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return ts;
    }
  };

  const fmtTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  const statusConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string }> = {
    confirmed: { label: "Confirmed", color: "#00c977", bg: "#00c97715", border: "#00c97744", glow: "0 0 12px rgba(0,201,119,0.15)" },
    pending:   { label: "Pending",   color: "#ffb300", bg: "#ffb30015", border: "#ffb30044", glow: "0 0 12px rgba(255,179,0,0.15)" },
    cancelled: { label: "Cancelled", color: "#ff4455", bg: "#ff445515", border: "#ff445544", glow: "none" },
    expired:   { label: "Expired",   color: "#9ba3b5", bg: "#9ba3b515", border: "#9ba3b544", glow: "none" },
  };
  // Unknown statuses get a neutral badge with their own name, never "Pending"
  const neutralStatus = (status: string) => ({
    label: status ? status.charAt(0).toUpperCase() + status.slice(1) : "Unknown",
    color: "#9ba3b5", bg: "#9ba3b515", border: "#9ba3b544", glow: "none",
  });

  const filteredBookings = useMemo(() => {
    const now = new Date();
    return bookings.filter((b) => {
      const showTime = b.start_time ? new Date(b.start_time) : null;
      if (activeTab === "all") return true;
      if (activeTab === "upcoming") {
        return b.status === "confirmed" && showTime && showTime > now;
      }
      if (activeTab === "completed") {
        return b.status === "confirmed" && showTime && showTime <= now;
      }
      if (activeTab === "cancelled") {
        return b.status === "cancelled";
      }
      if (activeTab === "refund_pending") {
        return (
          b.status === "cancelled" &&
          (b.refund_status === "initiated" || b.refund_status === "pending" || b.refund_status === "retry_scheduled")
        );
      }
      if (activeTab === "refunded") {
        return b.refund_status === "processed";
      }
      return true;
    });
  }, [bookings, activeTab]);

  const counts = useMemo(() => {
    const now = new Date();
    return {
      all: bookings.length,
      upcoming: bookings.filter((b) => b.status === "confirmed" && b.start_time && new Date(b.start_time) > now).length,
      completed: bookings.filter((b) => b.status === "confirmed" && b.start_time && new Date(b.start_time) <= now).length,
      cancelled: bookings.filter((b) => b.status === "cancelled").length,
      refund_pending: bookings.filter(
        (b) =>
          b.status === "cancelled" &&
          (b.refund_status === "initiated" || b.refund_status === "pending" || b.refund_status === "retry_scheduled")
      ).length,
      refunded: bookings.filter((b) => b.refund_status === "processed").length,
    };
  }, [bookings]);

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

  const tabs: { key: FilterTab; label: string; count: number }[] = [
    { key: "all", label: "All Bookings", count: counts.all },
    { key: "upcoming", label: "Upcoming", count: counts.upcoming },
    { key: "completed", label: "Completed", count: counts.completed },
    { key: "cancelled", label: "Cancelled", count: counts.cancelled },
    { key: "refund_pending", label: "Refund Pending", count: counts.refund_pending },
    { key: "refunded", label: "Refunded", count: counts.refunded },
  ];

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
          padding: "40px 24px 20px",
        }}
      >
        <div style={{ maxWidth: 840, margin: "0 auto" }}>
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
                {bookings.length} total booking{bookings.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          {/* Filter Tabs */}
          <div
            style={{
              display: "flex",
              gap: 8,
              overflowX: "auto",
              paddingTop: 24,
              paddingBottom: 4,
              scrollbarWidth: "none",
            }}
          >
            {tabs.map((tab) => {
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "7px 14px",
                    borderRadius: 999,
                    fontSize: 13,
                    fontWeight: active ? 700 : 500,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    background: active ? "var(--blue, #287cff)" : "var(--surface, #11141e)",
                    color: active ? "#fff" : "var(--muted, #9ba3b5)",
                    border: `1px solid ${active ? "var(--blue, #287cff)" : "var(--border, #292e3d)"}`,
                    transition: "all 0.15s ease",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span>{tab.label}</span>
                  <span
                    style={{
                      fontSize: 11,
                      padding: "1px 6px",
                      borderRadius: 999,
                      background: active ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.06)",
                      color: active ? "#fff" : "inherit",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 840, margin: "0 auto", padding: "32px 24px" }}>
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
        ) : filteredBookings.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "60px 24px",
              background: "var(--surface, #11141e)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 16,
              color: "var(--muted, #9ba3b5)",
            }}
          >
            <p style={{ fontSize: 16, fontWeight: 600, margin: "0 0 8px", color: "var(--foreground, #fff)" }}>
              No bookings in this filter
            </p>
            <p style={{ fontSize: 13, margin: "0 0 16px" }}>
              Try selecting another filter tab to view your bookings.
            </p>
            <button
              onClick={() => setActiveTab("all")}
              style={{
                background: "transparent",
                border: "1px solid var(--border, #292e3d)",
                color: "var(--foreground, #fff)",
                padding: "8px 16px",
                borderRadius: 8,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              View All Bookings
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {filteredBookings.map((b) => {
              const sc = statusConfig[b.status] ?? neutralStatus(b.status);
              const isCancelled = b.status === "cancelled";
              const refundAmt = Number(b.refund_amount || 0);

              let refundBadge: { label: string; bg: string; color: string; border: string } | null = null;
              if (isCancelled) {
                if (b.refund_status === "processed") {
                  refundBadge = {
                    label: `✓ Refunded ₹${refundAmt.toFixed(2)}`,
                    bg: "rgba(16, 185, 129, 0.15)",
                    color: "#34d399",
                    border: "rgba(16, 185, 129, 0.35)",
                  };
                } else if (b.refund_status === "initiated" || b.refund_status === "pending" || b.refund_status === "retry_scheduled") {
                  refundBadge = {
                    label: `⏳ Refund Pending ₹${refundAmt.toFixed(2)}`,
                    bg: "rgba(245, 158, 11, 0.15)",
                    color: "#fbbf24",
                    border: "rgba(245, 158, 11, 0.35)",
                  };
                } else if (b.refund_status === "failed") {
                  refundBadge = {
                    label: "⚠ Refund Issue — Needs Review",
                    bg: "rgba(239, 68, 68, 0.15)",
                    color: "#f87171",
                    border: "rgba(239, 68, 68, 0.35)",
                  };
                } else if (b.refund_status === "non_refundable" || refundAmt === 0) {
                  refundBadge = {
                    label: "Non-refundable",
                    bg: "rgba(107, 114, 128, 0.15)",
                    color: "#9ca3af",
                    border: "rgba(107, 114, 128, 0.35)",
                  };
                }
              }
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
                      border: `1px solid ${isCancelled ? "rgba(255,68,85,0.25)" : "var(--border, #292e3d)"}`,
                      borderRadius: 16,
                      padding: "18px 20px",
                      display: "flex",
                      gap: 16,
                      alignItems: "flex-start",
                      transition: "transform 0.18s, border-color 0.18s, box-shadow 0.18s",
                      opacity: isCancelled ? 0.92 : 1,
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
                        opacity: isCancelled ? 0.6 : 0.85,
                      }}
                    />

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 3 }}>
                            <h3
                              style={{
                                fontSize: 16,
                                fontWeight: 700,
                                color: "var(--foreground, #f4f6fb)",
                                margin: 0,
                              }}
                              className="booking-title"
                            >
                              {b.event_title || "Booking"}
                            </h3>
                            {refundBadge && (
                              <span
                                style={{
                                  fontSize: 11,
                                  fontWeight: 600,
                                  padding: "2px 8px",
                                  borderRadius: 6,
                                  background: refundBadge.bg,
                                  color: refundBadge.color,
                                  border: `1px solid ${refundBadge.border}`,
                                }}
                              >
                                {refundBadge.label}
                              </span>
                            )}
                          </div>
                          <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: "0 0 2px" }}>
                            📍 {b.venue_name}{b.city ? `, ${b.city}` : ""}
                          </p>
                          <p style={{ fontSize: 13, color: "var(--muted, #9ba3b5)", margin: 0 }}>
                            🕐 {fmtDate(b.start_time)} · {fmtTime(b.start_time)}
                          </p>
                          {isCancelled && b.cancellation_reason && (
                            <p style={{ fontSize: 12, color: "#f87171", margin: "4px 0 0" }}>
                              Reason: {b.cancellation_reason}
                            </p>
                          )}
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
                              color: isCancelled ? "var(--muted, #9ba3b5)" : "var(--blue, #287cff)",
                              letterSpacing: "-0.01em",
                              textDecoration: isCancelled ? "line-through" : "none",
                            }}
                          >
                            ₹{parseFloat(b.total_amount).toFixed(2)}
                          </span>

                          {isCancelled ? (
                            <span
                              style={{
                                color: "var(--blue, #287cff)",
                                fontSize: 12,
                                fontWeight: 700,
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              View Refund Details →
                            </span>
                          ) : b.status === "pending" ? (
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
                          ) : null}
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
