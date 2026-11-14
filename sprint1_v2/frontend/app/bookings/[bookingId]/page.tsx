"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { bookingsApi } from "@/lib/api";
import { cancellationsApi, CancelEligibility } from "@/lib/cancellationsApi";
import { useAuth } from "@/contexts/AuthContext";
import toast from "react-hot-toast";
import Link from "next/link";

/* ── tiny helpers ───────────────────────────────────────────── */
function fmtDate(iso: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const SEAT_TYPE_COLORS: Record<string, string> = {
  premium:   "var(--gold)",
  gold:      "var(--gold)",
  vip:       "var(--gold)",
  recliner:  "var(--gold)",
  silver:    "var(--silver)",
  standard:  "var(--silver)",
  general:   "var(--silver)",
};

function SeatChip({ s }: { s: any }) {
  const color = SEAT_TYPE_COLORS[s.seat_type?.toLowerCase()] ?? "var(--silver)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: `${color}22`,
        border: `1px solid ${color}66`,
        color,
        letterSpacing: "0.03em",
      }}
    >
      {s.row_label}{s.seat_number}
      <span style={{ opacity: 0.6, fontWeight: 400, fontSize: 10 }}>
        {s.seat_type}
      </span>
    </span>
  );
}

/* ── status pill ────────────────────────────────────────────── */
const STATUS_META: Record<string, { bg: string; color: string; label: string }> = {
  confirmed: { bg: "#00c97722", color: "#00c977", label: "CONFIRMED" },
  pending:   { bg: "#ffb30022", color: "#ffb300", label: "PENDING" },
  cancelled: { bg: "#ff334422", color: "#ff3344", label: "CANCELLED" },
  expired:   { bg: "#9ba3b522", color: "#9ba3b5", label: "EXPIRED" },
};

function StatusPill({ status }: { status: string }) {
  const m = STATUS_META[status] ?? { bg: "#9ba3b522", color: "#9ba3b5", label: status.toUpperCase() };
  return (
    <span
      style={{
        padding: "4px 14px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.08em",
        background: m.bg,
        color: m.color,
        border: `1px solid ${m.color}44`,
      }}
    >
      {m.label}
    </span>
  );
}

/* ── perforated divider ─────────────────────────────────────── */
function TicketDivider() {
  return (
    <div style={{ display: "flex", alignItems: "center", margin: "20px 0", gap: 0 }}>
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          background: "var(--background)",
          marginLeft: -30,
          flexShrink: 0,
          border: "1px solid var(--border)",
        }}
      />
      <div
        style={{
          flex: 1,
          borderTop: "2px dashed var(--border)",
          margin: "0 8px",
        }}
      />
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          background: "var(--background)",
          marginRight: -30,
          flexShrink: 0,
          border: "1px solid var(--border)",
        }}
      />
    </div>
  );
}

/* ── main page ──────────────────────────────────────────────── */
export default function BookingDetailPage() {
  const { bookingId } = useParams<{ bookingId: string }>();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);

  const [eligibility, setEligibility] = useState<CancelEligibility | null>(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const loadBooking = useCallback(() => {
    if (user && bookingId) {
      bookingsApi
        .get(bookingId)
        .then((b) => {
          setBooking(b);
          if (b.status === "confirmed") {
            cancellationsApi
              .checkEligibility(bookingId)
              .then(setEligibility)
              .catch(() => setEligibility(null));
          }
        })
        .catch(() => toast.error("Booking not found"))
        .finally(() => setLoading(false));
    }
  }, [user, bookingId]);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    loadBooking();
  }, [user, authLoading, loadBooking, router]);

  const handleDownloadPdf = async () => {
    if (!user) { toast.error("Please log in again"); return; }
    setDownloading(true);
    try {
      const token = await user.getIdToken();
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${API_URL}/api/tickets/bookings/${bookingId}/pdf`,
        { method: "GET", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) {
        const msgs: Record<number, string> = { 403: "Authentication failed.", 404: "Ticket not found." };
        toast.error(msgs[response.status] ?? "Could not download ticket PDF");
        return;
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ticket_${bookingId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Ticket PDF downloaded");
    } catch {
      toast.error("Could not download ticket PDF");
    } finally {
      setDownloading(false);
    }
  };

  const handleConfirmCancel = async () => {
    setCancelling(true);
    try {
      const result = await cancellationsApi.cancel(bookingId);
      setShowCancelModal(false);
      toast.success("Booking cancelled");
      setLoading(true);
      loadBooking();
      if (result.refund_initiated) {
        toast.success(
          `Refund of ₹${result.refund_amount.toFixed(2)} initiated — allow 5–7 business days`,
          { duration: 6000 }
        );
      }
    } catch (err: any) {
      toast.error(err?.message || "Cancellation failed");
    } finally {
      setCancelling(false);
    }
  };

  const copyBookingId = () => {
    navigator.clipboard.writeText(bookingId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  /* ── loading / empty states ─────────────────────────────── */
  if (loading || authLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", gap: 16 }}>
        <div style={{ width: 36, height: 36, borderRadius: "50%", border: "3px solid var(--blue)", borderTopColor: "transparent", animation: "spin 0.8s linear infinite" }} />
        <p style={{ color: "var(--muted)", fontSize: 14 }}>Loading your booking…</p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    );
  }

  if (!booking) {
    return (
      <div style={{ textAlign: "center", padding: "80px 16px" }}>
        <p style={{ color: "#ff3344", marginBottom: 16 }}>Booking not found.</p>
        <Link href="/bookings" className="btn-secondary">← My Bookings</Link>
      </div>
    );
  }

  const seats: any[] = Array.isArray(booking.seats_info)
    ? booking.seats_info.filter(Boolean)
    : [];

  const totalSeats = seats.length;
  const isCancelled = booking.status === "cancelled";
  const isConfirmed = booking.status === "confirmed";

  return (
    <>
      <style>{`
        .ticket-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 20px;
          overflow: visible;
          position: relative;
          box-shadow: 0 8px 40px rgba(0,0,0,0.5);
        }
        .hero-band {
          position: relative;
          border-radius: 20px 20px 0 0;
          overflow: hidden;
          min-height: 180px;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          padding: 24px;
        }
        .hero-bg {
          position: absolute;
          inset: 0;
          object-fit: cover;
          width: 100%;
          height: 100%;
          filter: blur(4px) brightness(0.35) saturate(1.2);
          transform: scale(1.08);
        }
        .hero-gradient {
          position: absolute;
          inset: 0;
          background: linear-gradient(to top, var(--surface) 0%, transparent 60%);
        }
        .hero-fallback {
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg, #1a1f30 0%, #0d1020 100%);
        }
        .hero-content { position: relative; z-index: 1; }
        .info-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 0;
          border-bottom: 1px solid var(--border);
          font-size: 14px;
        }
        .info-row:last-child { border-bottom: none; }
        .info-label { color: var(--muted); }
        .info-value { color: var(--foreground); font-weight: 500; text-align: right; max-width: 60%; }
        .action-btn {
          width: 100%;
          padding: 13px 20px;
          border-radius: 12px;
          font-size: 15px;
          font-weight: 700;
          cursor: pointer;
          transition: opacity 0.15s, transform 0.1s;
          border: none;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          text-decoration: none;
        }
        .action-btn:active { transform: scale(0.98); }
        .action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-download {
          background: var(--blue);
          color: #fff;
        }
        .btn-download:hover:not(:disabled) { background: var(--blue-hover, #4a91ff); }
        .btn-cancel {
          background: transparent;
          color: #ff5566;
          border: 1.5px solid #ff334440;
        }
        .btn-cancel:hover:not(:disabled) { background: #ff334410; border-color: #ff334480; }
        .btn-allbookings {
          background: var(--surface-raised);
          color: var(--foreground);
          border: 1px solid var(--border);
        }
        .btn-allbookings:hover { background: var(--border); }
        .cancelled-banner {
          background: #ff334412;
          border: 1px solid #ff334430;
          border-radius: 12px;
          padding: 16px;
          text-align: center;
        }
        .modal-overlay {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.75);
          display: flex; align-items: center; justify-content: center;
          z-index: 100; padding: 16px;
          backdrop-filter: blur(4px);
        }
        .modal-box {
          background: var(--surface-raised);
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 28px 24px;
          width: 100%;
          max-width: 380px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }
        .modal-icon {
          width: 52px; height: 52px;
          border-radius: 50%;
          background: #ff334420;
          border: 1px solid #ff334440;
          display: flex; align-items: center; justify-content: center;
          margin: 0 auto 16px;
          font-size: 24px;
        }
        :root { --gold: #f5b942; --silver: #9ba3b5; }
      `}</style>

      <div style={{ maxWidth: 480, margin: "0 auto", padding: "24px 16px 60px" }}>

        {/* back link */}
        <Link
          href="/bookings"
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            color: "var(--muted)", fontSize: 13, marginBottom: 20,
            textDecoration: "none", fontWeight: 500,
          }}
        >
          ← My Bookings
        </Link>

        {/* ── TICKET CARD ── */}
        <div className="ticket-card">

          {/* hero band */}
          <div className="hero-band">
            {booking.poster_url ? (
              <img src={booking.poster_url} className="hero-bg" alt="" />
            ) : (
              <div className="hero-fallback" />
            )}
            <div className="hero-gradient" />
            <div className="hero-content">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <h1 style={{ fontSize: 22, fontWeight: 800, color: "#fff", lineHeight: 1.2, margin: 0, textShadow: "0 1px 8px rgba(0,0,0,0.6)" }}>
                  {booking.event_title ?? "Your Booking"}
                </h1>
                <StatusPill status={booking.status} />
              </div>
              {(booking.venue_name || booking.city) && (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "rgba(255,255,255,0.65)", display: "flex", alignItems: "center", gap: 4 }}>
                  📍 {[booking.venue_name, booking.city].filter(Boolean).join(", ")}
                </p>
              )}
              {booking.start_time && (
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "rgba(255,255,255,0.65)", display: "flex", alignItems: "center", gap: 4 }}>
                  🕐 {fmtDate(booking.start_time)}
                </p>
              )}
            </div>
          </div>

          {/* ── ticket body ── */}
          <div style={{ padding: "0 24px 24px" }}>

            <TicketDivider />

            {/* booking number */}
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 11, color: "var(--muted)", letterSpacing: "0.08em", fontWeight: 600, marginBottom: 6 }}>BOOKING NUMBER</p>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontFamily: "monospace", fontSize: 15, color: "var(--foreground)", letterSpacing: "0.06em", fontWeight: 700 }}>
                  {bookingId.slice(0, 8).toUpperCase()}–{bookingId.slice(9, 13).toUpperCase()}
                </span>
                <button
                  onClick={copyBookingId}
                  title="Copy booking ID"
                  style={{
                    background: copied ? "#00c97720" : "var(--surface-raised)",
                    border: `1px solid ${copied ? "#00c97740" : "var(--border)"}`,
                    borderRadius: 6,
                    color: copied ? "#00c977" : "var(--muted)",
                    fontSize: 11,
                    padding: "3px 8px",
                    cursor: "pointer",
                    fontWeight: 600,
                    transition: "all 0.2s",
                  }}
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            {/* seats */}
            {seats.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <p style={{ fontSize: 11, color: "var(--muted)", letterSpacing: "0.08em", fontWeight: 600, marginBottom: 8 }}>
                  SEATS · {totalSeats} {totalSeats === 1 ? "TICKET" : "TICKETS"}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {seats.map((s: any, i: number) => (
                    <SeatChip key={i} s={s} />
                  ))}
                </div>
              </div>
            )}

            {/* info rows */}
            <div style={{ background: "var(--surface-raised)", borderRadius: 12, padding: "4px 16px", marginBottom: 20 }}>
              {booking.screen_name && (
                <div className="info-row">
                  <span className="info-label">Screen</span>
                  <span className="info-value">{booking.screen_name}</span>
                </div>
              )}
              <div className="info-row">
                <span className="info-label">Booked on</span>
                <span className="info-value">{fmtDate(booking.created_at)}</span>
              </div>
              {isCancelled && booking.cancelled_at && (
                <div className="info-row">
                  <span className="info-label">Cancelled on</span>
                  <span className="info-value" style={{ color: "#ff5566" }}>{fmtDate(booking.cancelled_at)}</span>
                </div>
              )}
              <div className="info-row" style={{ borderBottom: "none" }}>
                <span className="info-label" style={{ fontWeight: 700, color: "var(--foreground)" }}>Total Paid</span>
                <span style={{ fontSize: 20, fontWeight: 800, color: "var(--blue)" }}>
                  ₹{parseFloat(booking.total_amount).toFixed(2)}
                </span>
              </div>
            </div>

            {/* ── action zone ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {isConfirmed && (
                <>
                  <button
                    onClick={handleDownloadPdf}
                    disabled={downloading}
                    className="action-btn btn-download"
                  >
                    {downloading ? (
                      <>
                        <span style={{ width: 16, height: 16, border: "2px solid #fff", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                        Downloading…
                      </>
                    ) : (
                      <>⬇ Download Ticket PDF</>
                    )}
                  </button>

                  {eligibility?.eligible && (
                    <button
                      onClick={() => setShowCancelModal(true)}
                      className="action-btn btn-cancel"
                    >
                      Cancel Booking
                    </button>
                  )}
                  {eligibility && !eligibility.eligible && (
                    <p style={{ textAlign: "center", fontSize: 12, color: "var(--muted)", padding: "4px 0" }}>
                      🔒 {eligibility.reason}
                    </p>
                  )}
                </>
              )}

              {booking.status === "pending" && (
                <Link
                  href={`/payment?booking_id=${bookingId}`}
                  className="action-btn btn-download"
                  style={{ textDecoration: "none" }}
                >
                  💳 Complete Payment
                </Link>
              )}

              {isCancelled && (
                <div className="cancelled-banner">
                  <p style={{ color: "#ff5566", fontWeight: 700, margin: "0 0 4px" }}>Booking Cancelled</p>
                  <p style={{ color: "var(--muted)", fontSize: 13, margin: 0 }}>
                    If a payment was made, your refund will arrive in 5–7 business days.
                  </p>
                </div>
              )}

              <Link
                href="/bookings"
                className="action-btn btn-allbookings"
                style={{ textDecoration: "none", marginTop: 2 }}
              >
                All Bookings
              </Link>

              <Link
                href={`/support/new?booking_id=${bookingId}&category=booking`}
                style={{ textAlign: "center", fontSize: 12, color: "var(--muted)", padding: "4px 0", textDecoration: "none" }}
              >
                Need help? Contact support →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ── CANCEL MODAL ── */}
      {showCancelModal && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowCancelModal(false); }}>
          <div className="modal-box">
            <div className="modal-icon">🎟️</div>
            <h2 style={{ textAlign: "center", fontWeight: 800, fontSize: 18, margin: "0 0 10px", color: "var(--foreground)" }}>
              Cancel this booking?
            </h2>
            <p style={{ textAlign: "center", color: "var(--muted)", fontSize: 14, lineHeight: 1.6, margin: "0 0 24px" }}>
              This action cannot be undone.
              {eligibility?.has_payment && eligibility?.refund_amount ? (
                <>
                  {" "}A refund of{" "}
                  <span style={{ color: "var(--foreground)", fontWeight: 700 }}>
                    ₹{eligibility.refund_amount.toFixed(2)}
                  </span>{" "}
                  will be initiated to your original payment method (5–7 business days).
                </>
              ) : (
                " No payment is on record for this booking."
              )}
            </p>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                style={{
                  flex: 1, padding: "13px", borderRadius: 12,
                  background: "var(--surface)", border: "1px solid var(--border)",
                  color: "var(--foreground)", fontWeight: 600, fontSize: 14, cursor: "pointer",
                }}
              >
                Keep It
              </button>
              <button
                onClick={handleConfirmCancel}
                disabled={cancelling}
                style={{
                  flex: 1, padding: "13px", borderRadius: 12,
                  background: "#ff3344", border: "none",
                  color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer",
                  opacity: cancelling ? 0.6 : 1,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                }}
              >
                {cancelling ? (
                  <><span style={{ width: 15, height: 15, border: "2px solid #fff", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.7s linear infinite", display: "inline-block" }} /> Cancelling…</>
                ) : "Yes, Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
