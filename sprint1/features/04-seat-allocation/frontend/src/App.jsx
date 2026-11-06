/**
 * App.jsx — Main orchestrator
 * ============================
 * Manages the full booking flow across all 7 phases:
 *
 *  Phase 1: Loads from fixture data via API
 *  Phase 2: Renders seat map
 *  Phase 3: Atomic lock on "Hold Seats"
 *  Phase 4: Countdown timer; auto-expired-lock detection
 *  Phase 5: Payment → Confirm transition; Cancel releases seats
 *  Phase 6: WebSocket updates applied to seat store in real-time
 *  Phase 7: Expired-lock UX shown on confirm failure
 *
 * State machine:
 *  'browsing' → 'locked' → 'payment' → 'confirmed'
 *                    ↓ (expired)
 *                 'expired'
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from './api';
import { useWebSocket } from './hooks/useWebSocket';
import { useToast } from './hooks/useToast';

import { Header } from './components/Header';
import { SeatMap } from './components/SeatMap';
import { CheckoutSidebar } from './components/Sidebar';
import { PaymentScreen } from './components/PaymentScreen';
import { ConfirmationScreen } from './components/ConfirmationScreen';
import { ExpiredScreen } from './components/ExpiredScreen';
import { BookingsPage } from './components/BookingsPage';
import { ToastContainer } from './components/Toast';

// ─── Constants ──────────────────────────────────────────────────────────────
const DEMO_SHOW_ID = 'show-demo-001';
const DEMO_USER_ID = 'user-demo-khushi';
const MAX_SEATS = 6;

// ─── Show metadata (would come from the shows API in a real app) ─────────────
const SHOW_INFO = {
  title: 'Dune: Prophecy — Special Screening',
  date: 'Sunday, 13 Oct 2026',
  time: '7:00 PM',
  venue: 'Cineplex IMAX, Mumbai',
  language: 'English (Subtitles)',
  rating: 'U/A',
  emoji: '🎬',
};

// ─── Flow states ─────────────────────────────────────────────────────────────
const STATE = {
  BROWSING: 'browsing',
  LOCKED: 'locked',
  PAYMENT: 'payment',
  CONFIRMED: 'confirmed',
  EXPIRED: 'expired',
};

export default function App() {
  // ── Navigation ─────────────────────────────────────────────────────────
  const [page, setPage] = useState('seat-map'); // 'seat-map' | 'bookings'

  // ── Seats state ────────────────────────────────────────────────────────
  const [seats, setSeats] = useState([]);
  const [loadingSeats, setLoadingSeats] = useState(true);

  // ── Selection state ────────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState(new Set());

  // ── Flow state ─────────────────────────────────────────────────────────
  const [flowState, setFlowState] = useState(STATE.BROWSING);
  const [lockInfo, setLockInfo] = useState(null);   // { locked_seat_ids, expires_at }
  const [booking, setBooking] = useState(null);   // confirmed booking object
  const [isLocking, setIsLocking] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);

  // ── Toast ───────────────────────────────────────────────────────────────
  const { toasts, showToast, dismiss } = useToast();

  // ── Load seats ──────────────────────────────────────────────────────────
  const loadSeats = useCallback(async () => {
    setLoadingSeats(true);
    try {
      const data = await api.getSeats(DEMO_SHOW_ID);
      setSeats(data.seats);
    } catch (e) {
      showToast('Connection error', 'Could not load seats. Is the backend running?', 'error', 8000);
    } finally {
      setLoadingSeats(false);
    }
  }, []);

  useEffect(() => { loadSeats(); }, [loadSeats]);

  // ── Phase 6: Real-time WebSocket seat updates ──────────────────────────
  const handleSeatUpdate = useCallback((seatId, newStatus) => {
    setSeats(prev => prev.map(s =>
      s.id === seatId ? { ...s, status: newStatus } : s
    ));
    // If this seat was selected by current user and it became available again
    // (lock released by sweeper), remove from selection
    if (newStatus === 'available') return;
    if (newStatus === 'locked' || newStatus === 'booked') {
      setSelectedIds(prev => {
        if (!prev.has(seatId)) return prev;
        const next = new Set(prev);
        next.delete(seatId);
        showToast('Seat taken', `Seat ${seatId} was just grabbed by someone else.`, 'warning');
        return next;
      });
    }
  }, [showToast]);

  const wsStatus = useWebSocket(DEMO_SHOW_ID, handleSeatUpdate);

  // ── Derived seat objects for selected IDs ──────────────────────────────
  const selectedSeats = seats.filter(s => selectedIds.has(s.id));
  const totalAmount = (() => {
    const sub = selectedSeats.reduce((sum, s) => sum + s.price, 0);
    const fee = Math.round(sub * 0.02);
    return sub + fee;
  })();

  // ── Phase 2: Toggle seat selection ────────────────────────────────────
  const handleToggleSeat = useCallback((seat) => {
    if (flowState !== STATE.BROWSING) return;
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(seat.id)) {
        next.delete(seat.id);
      } else {
        if (next.size >= MAX_SEATS) {
          showToast('Max seats reached', `You can only select up to ${MAX_SEATS} seats per booking.`, 'warning');
          return prev;
        }
        next.add(seat.id);
      }
      return next;
    });
  }, [flowState, showToast]);

  // ── Phase 3: Atomic lock ───────────────────────────────────────────────
  const handleHoldSeats = async () => {
    if (selectedIds.size === 0) return;
    setIsLocking(true);
    try {
      const result = await api.lockSeats(DEMO_SHOW_ID, [...selectedIds], DEMO_USER_ID);
      setLockInfo(result);
      setFlowState(STATE.LOCKED);
      showToast('Seats held! 🔒', `You have 5 minutes to complete payment.`, 'success');
    } catch (e) {
      if (e.status === 409) {
        // Some seats were grabbed — update their visual status
        const failedIds = e.detail?.failed_seat_ids || [];
        setSeats(prev => prev.map(s =>
          failedIds.includes(s.id) ? { ...s, status: 'locked' } : s
        ));
        // Remove failed from selection
        setSelectedIds(prev => {
          const next = new Set(prev);
          failedIds.forEach(id => next.delete(id));
          return next;
        });
        showToast('Seats no longer available', e.message, 'error');
      } else {
        showToast('Error', e.message, 'error');
      }
    } finally {
      setIsLocking(false);
    }
  };

  // ── Phase 4: Manual release / cancel selection ─────────────────────────
  const handleCancelSelection = async () => {
    if (flowState === STATE.LOCKED && lockInfo) {
      // Release the lock on the backend
      try {
        await api.releaseSeats(DEMO_SHOW_ID, lockInfo.locked_seat_ids, DEMO_USER_ID);
        showToast('Seats released', 'Your selection has been cleared.', 'info');
      } catch (e) {
        // Best-effort; proceed anyway
      }
    }
    setSelectedIds(new Set());
    setLockInfo(null);
    setFlowState(STATE.BROWSING);
    loadSeats();
  };

  // ── Phase 4: Lock expired (detected by countdown timer) ───────────────
  const lockExpiredRef = useRef(false);
  const handleLockExpired = useCallback(() => {
    if (lockExpiredRef.current) return; // only once
    lockExpiredRef.current = true;
    setFlowState(STATE.EXPIRED);
    showToast('Hold expired ⌛', 'Your seat hold has expired. Please re-select.', 'warning', 6000);
  }, [showToast]);

  // ── Phase 5: Proceed to payment ───────────────────────────────────────
  const handleProceedToPayment = () => {
    setFlowState(STATE.PAYMENT);
  };

  // ── Phase 5: After payment success — confirm booking ──────────────────
  const handlePaymentSuccess = async () => {
    setIsConfirming(true);
    try {
      const result = await api.confirmSeats(
        DEMO_SHOW_ID,
        lockInfo.locked_seat_ids,
        DEMO_USER_ID,
      );
      setBooking(result.booking);
      setFlowState(STATE.CONFIRMED);
      showToast('Booking confirmed! 🎉', `Booking ID: ${result.booking.booking_id}`, 'success', 6000);
    } catch (e) {
      if (e.status === 409 && e.detail?.error_code === 'LOCK_EXPIRED') {
        // Phase 7: Lock expired between payment and confirm
        setFlowState(STATE.EXPIRED);
        showToast('Hold expired during payment', e.message, 'error', 8000);
      } else {
        showToast('Confirmation failed', e.message, 'error');
      }
    } finally {
      setIsConfirming(false);
    }
  };

  // ── Phase 7: Retry selection ──────────────────────────────────────────
  const handleRetrySelection = () => {
    lockExpiredRef.current = false;
    setSelectedIds(new Set());
    setLockInfo(null);
    setFlowState(STATE.BROWSING);
    loadSeats();
  };

  // ── Page: Seat Map ─────────────────────────────────────────────────────
  const renderSeatMapPage = () => (
    <>
      {/* Show info banner */}
      <div className="show-banner">
        <div className="show-banner-inner">
          <div className="show-poster">{SHOW_INFO.emoji}</div>
          <div className="show-info">
            <h1 className="show-title">{SHOW_INFO.title}</h1>
            <div className="show-meta">
              <span className="show-meta-item">📅 {SHOW_INFO.date}</span>
              <span className="show-meta-item">🕐 {SHOW_INFO.time}</span>
              <span className="show-meta-item">📍 {SHOW_INFO.venue}</span>
              <span className="show-meta-item">🌐 {SHOW_INFO.language}</span>
              <span className="show-badge badge-live">Live Availability</span>
            </div>
          </div>
        </div>
      </div>

      <div className="main-layout">
        {/* Left: seat map */}
        <div className="seat-map-area">
          {flowState === STATE.EXPIRED ? (
            <ExpiredScreen
              expiredSeatIds={lockInfo?.locked_seat_ids}
              onRetry={handleRetrySelection}
            />
          ) : flowState === STATE.CONFIRMED ? (
            <ConfirmationScreen
              booking={booking}
              onViewBookings={() => setPage('bookings')}
              onBookAgain={handleRetrySelection}
            />
          ) : flowState === STATE.PAYMENT ? (
            <PaymentScreen
              selectedSeats={selectedSeats}
              lockInfo={lockInfo}
              totalAmount={totalAmount}
              onPaymentSuccess={handlePaymentSuccess}
              onBack={() => setFlowState(STATE.LOCKED)}
            />
          ) : (
            <SeatMap
              seats={seats}
              selectedIds={selectedIds}
              onToggle={handleToggleSeat}
              maxSeats={MAX_SEATS}
              loading={loadingSeats}
            />
          )}
        </div>

        {/* Right: sidebar (hidden during payment/confirmation/expired for cleaner UX) */}
        {(flowState === STATE.BROWSING || flowState === STATE.LOCKED) && (
          <CheckoutSidebar
            selectedSeats={selectedSeats}
            maxSeats={MAX_SEATS}
            lockInfo={lockInfo}
            onRemoveSeat={(id) => {
              if (flowState !== STATE.BROWSING) return;
              setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
            }}
            onProceed={flowState === STATE.LOCKED ? handleProceedToPayment : handleHoldSeats}
            onCancelSelection={handleCancelSelection}
            onLockExpired={handleLockExpired}
            isLocking={isLocking}
            wsStatus={wsStatus}
          />
        )}
      </div>
    </>
  );

  return (
    <div className="app-shell">
      <Header currentPage={page} onNavigate={setPage} />

      <main>
        {page === 'bookings' ? (
          <BookingsPage showToast={showToast} />
        ) : (
          renderSeatMapPage()
        )}
      </main>

      <ToastContainer toasts={toasts} dismiss={dismiss} />
    </div>
  );
}
