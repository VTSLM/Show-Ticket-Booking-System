'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './PaymentCheckout.css';

const methodNames = { upi: 'UPI', card: 'Card', netbanking: 'Net banking', wallet: 'Wallet', paylater: 'Pay later', emi: 'EMI', app: 'App' };
const terminalFailure = new Set(['failed', 'cancelled']);
const unresolved = new Set(['created', 'verification_pending', 'authorized', 'successful_needs_review']);

function displayDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(date);
}
function displayTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' }).format(date) + ' IST';
  return String(value);
}
function displayTimestamp(value) {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(date) + ' IST';
}
function displayMethod(value) {
  if (!value) return 'Not available yet';
  const normalized = String(value).toLowerCase();
  return methodNames[normalized] || normalized.replace(/[_-]/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function formatDateTime(value) { return value ? displayTimestamp(value) : 'Not available'; }

/**
 * Feature 05 integration component for the team's React/Next.js frontend.
 *
 * Required props:
 * - bookingId: canonical pending booking UUID created by Feature 04.
 * - getAccessToken: async function returning Firebase Auth user's ID token.
 *
 * Optional props:
 * - apiBaseUrl: FastAPI base URL, e.g. process.env.NEXT_PUBLIC_BACKEND_URL.
 * - onBookingConfirmed(result): called only when backend reports booking confirmed.
 * - onPaymentResult(result): called on every reconciled payment state.
 */
export default function PaymentCheckout({
  bookingId,
  getAccessToken,
  apiBaseUrl = '',
  onBookingConfirmed,
  onPaymentResult,
}) {
  const [booking, setBooking] = useState(null);
  const [result, setResult] = useState(null);
  const [pendingOrder, setPendingOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const callbacks = useRef({ onBookingConfirmed, onPaymentResult });
  useEffect(() => { callbacks.current = { onBookingConfirmed, onPaymentResult }; }, [onBookingConfirmed, onPaymentResult]);
  const checkoutOpen = useRef(false);
  const verificationInFlight = useRef(false);
  const storageKey = useMemo(() => `cinepass.pendingRazorpayVerification:${bookingId || 'missing-booking'}`, [bookingId]);

  const api = useCallback(async (path, options = {}) => {
    const token = typeof getAccessToken === 'function' ? await getAccessToken() : '';
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    const baseUrl = String(apiBaseUrl || '').replace(/\/+$/, '');
    const response = await fetch(`${baseUrl}${path}`, { cache: 'no-store', ...options, headers });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
    return body;
  }, [apiBaseUrl, getAccessToken]);

  const rememberOrder = useCallback((orderId, paymentId = '') => {
    if (!orderId) return;
    const value = { order_id: orderId, payment_id: paymentId || '', booking_id: bookingId };
    setPendingOrder(value);
    try { window.sessionStorage.setItem(storageKey, JSON.stringify(value)); } catch { /* Session storage is optional; server-side unresolved-order guard remains. */ }
  }, [bookingId, storageKey]);

  const forgetOrder = useCallback(() => {
    setPendingOrder(null);
    try { window.sessionStorage.removeItem(storageKey); } catch { /* Session storage is optional. */ }
  }, [storageKey]);

  const updateResult = useCallback((data) => {
    setResult(data);
    if (data.booking) setBooking((old) => data.booking || old);
    callbacks.current.onPaymentResult?.(data);
    if (data.booking_confirmation_status === 'confirmed' || data.booking?.status === 'confirmed') {
      forgetOrder();
      callbacks.current.onBookingConfirmed?.(data);
    } else if (data.status === 'failed' || data.status === 'cancelled') {
      // These are provider-confirmed terminal states, not a browser dismissal.
      forgetOrder();
    } else if (data.status === 'successful_needs_review') {
      // Captured money with expired/reassigned seats must never lead to another charge.
      rememberOrder(data.order_id, data.payment?.payment_id || '');
    }
  }, [forgetOrder, rememberOrder]);

  const recheck = useCallback(async (orderId, paymentId = '') => {
    if (!orderId || verificationInFlight.current) return;
    verificationInFlight.current = true;
    setBusy(true);
    setError('');
    rememberOrder(orderId, paymentId);
    try {
      const data = await api(`/api/payments/orders/${encodeURIComponent(orderId)}/recheck`, {
        method: 'POST', body: JSON.stringify(paymentId ? { payment_id: paymentId } : {}),
      });
      updateResult(data);
    } catch (err) {
      setError(err.message || 'Could not check payment status. Keep this order and retry verification later.');
      setResult((old) => old || { order_id: orderId, status: 'verification_pending', payment: { payment_id: paymentId, status: 'verification_pending' } });
    } finally {
      setBusy(false);
      verificationInFlight.current = false;
    }
  }, [api, rememberOrder, updateResult]);

  useEffect(() => {
    let active = true;
    async function initialize() {
      if (!bookingId) {
        setError('A booking reference is required. Return from seat selection with the pending booking ID.');
        setLoading(false);
        return;
      }
      setLoading(true);
      setError('');
      try {
        const data = await api(`/api/payments/booking/${encodeURIComponent(bookingId)}`);
        if (!active) return;
        setBooking(data);
        let saved = null;
        try { saved = JSON.parse(window.sessionStorage.getItem(storageKey) || 'null'); } catch { saved = null; }
        if (saved?.order_id && saved.booking_id === bookingId) {
          setPendingOrder(saved);
          await recheck(saved.order_id, saved.payment_id || '');
        } else if (data.latest_payment?.order_id && data.latest_payment.status !== 'failed' && data.latest_payment.status !== 'cancelled') {
          setPendingOrder({ order_id: data.latest_payment.order_id, payment_id: data.latest_payment.payment?.payment_id || '', booking_id: bookingId });
          updateResult(data.latest_payment);
        }
      } catch (err) {
        if (active) setError(err.message || 'Unable to load this booking.');
      } finally {
        if (active) setLoading(false);
      }
    }
    initialize();
    return () => { active = false; };
  }, [api, bookingId, recheck, storageKey, updateResult]);

  const loadRazorpay = useCallback(() => new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return reject(new Error('Checkout is available in a browser only.'));
    if (window.Razorpay) return resolve();
    const existing = document.querySelector('script[data-cinepass-razorpay="true"]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Razorpay Checkout could not load. Check your internet connection.')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.dataset.cinepassRazorpay = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Razorpay Checkout could not load. Check your internet connection.'));
    document.head.appendChild(script);
  }), []);

  const openCheckout = useCallback(async (order) => {
    await loadRazorpay();
    const checkout = new window.Razorpay({
      key: order.key_id,
      amount: order.amount_paise,
      currency: order.currency || 'INR',
      name: 'Cinepass',
      description: `${booking?.event_title || 'Show booking'} · ${(booking?.seats || []).join(', ')}`,
      order_id: order.order_id,
      notes: { booking_number: booking?.booking_number || '' },
      theme: { color: '#8b7cff' },
      handler: async (response) => {
        checkoutOpen.current = false;
        setBusy(true);
        setResult({ order_id: order.order_id, status: 'verification_pending', payment: { status: 'verification_pending', payment_id: response.razorpay_payment_id } });
        rememberOrder(order.order_id, response.razorpay_payment_id);
        try {
          const data = await api(`/api/payments/orders/${encodeURIComponent(order.order_id)}/verify`, {
            method: 'POST', body: JSON.stringify(response),
          });
          updateResult(data);
        } catch (err) {
          setError(err.message || 'Verification is still pending. Do not pay again until this order is reconciled.');
          await recheck(order.order_id, response.razorpay_payment_id);
        } finally {
          setBusy(false);
        }
      },
      modal: {
        ondismiss: async () => {
          checkoutOpen.current = false;
          // Dismissal is not evidence of failure; check the same order first.
          await recheck(order.order_id, pendingOrder?.payment_id || '');
        },
      },
    });
    checkout.on('payment.failed', async (response) => {
      checkoutOpen.current = false;
      const metadata = response?.error?.metadata || {};
      const paymentId = metadata.payment_id || '';
      const orderId = metadata.order_id || order.order_id;
      try { checkout.close(); } catch { /* Checkout may already be closed. */ }
      await recheck(orderId, paymentId);
    });
    checkoutOpen.current = true;
    checkout.open();
  }, [api, booking, loadRazorpay, pendingOrder, recheck, rememberOrder, updateResult]);

  const beginPayment = useCallback(async () => {
    if (!booking || booking.status === 'confirmed' || busy) return;
    setError('');
    if (pendingOrder?.order_id) {
      await recheck(pendingOrder.order_id, pendingOrder.payment_id || '');
      return;
    }
    setBusy(true);
    let createdOrderId = '';
    try {
      const order = await api('/api/payments/orders', { method: 'POST', body: JSON.stringify({ booking_id: bookingId }) });
      if (order.provider !== 'razorpay' || !order.key_id) throw new Error('Razorpay Test Mode is not configured on the payment server.');
      createdOrderId = order.order_id;
      rememberOrder(order.order_id, '');
      await openCheckout(order);
    } catch (err) {
      const existing = String(err.message || '').match(/existing payment order needs reconciliation:\s*([A-Za-z0-9_-]+)/i);
      if (existing?.[1]) {
        rememberOrder(existing[1], '');
        await recheck(existing[1], '');
      } else if (createdOrderId) {
        // If the Checkout script failed after order creation, reconcile that exact
        // order before any retry is possible; do not drop an unresolved reference.
        await recheck(createdOrderId, '');
        setError(err.message || 'Checkout could not open. The existing order has been checked.');
      } else setError(err.message || 'Could not start checkout.');
    } finally {
      setBusy(false);
    }
  }, [api, booking, bookingId, busy, openCheckout, pendingOrder, recheck, rememberOrder]);

  const resultStatus = String(result?.payment?.status || result?.status || 'verification_pending').toLowerCase();
  const needsAttention = result?.booking_confirmation_status === 'needs_attention' || result?.status === 'successful_needs_review';
  const successful = !needsAttention && (resultStatus === 'successful' || resultStatus === 'captured' || result?.booking_confirmation_status === 'confirmed');
  const pending = needsAttention || unresolved.has(String(result?.status || resultStatus).toLowerCase()) || ['authorized', 'verification_pending', 'processing', 'created'].includes(resultStatus);
  const failed = !successful && !pending && terminalFailure.has(resultStatus);
  const statusLabel = successful ? 'SUCCESSFUL' : needsAttention ? 'REVIEW REQUIRED' : pending ? 'VERIFYING' : failed ? 'FAILED' : 'NOT CONFIRMED';

  if (loading) return <div className="cp-shell"><div className="cp-loading"><span className="cp-spinner" />Preparing your checkout…</div></div>;

  if (result) {
    return (
      <main className="cp-shell cp-result-shell">
        <div className={`cp-result-card ${successful ? 'is-success' : needsAttention ? 'is-review' : pending ? 'is-pending' : 'is-failure'}`}>
          <div className="cp-result-orb" aria-hidden="true">{successful ? '✓' : needsAttention ? '!' : pending ? '↻' : '×'}</div>
          <p className="cp-eyebrow">CINEPASS / PAYMENT STATUS</p>
          <h1>{successful ? 'Payment confirmed' : needsAttention ? 'Payment captured — booking needs attention' : pending ? 'Verifying your payment' : 'Payment not completed'}</h1>
          <p className="cp-result-message">
            {successful ? 'Your payment was verified and your booking is confirmed.' : needsAttention ? 'Razorpay reports that payment was captured, but the selected seats could not be confirmed. Do not pay again. The booking team must reconcile this transaction.' : pending ? 'We are checking this exact Razorpay order. Do not start another payment while the status is uncertain.' : 'The existing payment attempt was reconciled as unsuccessful. You can return to checkout if your booking and seat lock are still valid.'}
          </p>
          <span className={`cp-status-chip ${successful ? 'success' : needsAttention ? 'review' : pending ? 'pending' : 'failure'}`}>{statusLabel}</span>
          <div className="cp-transaction-grid">
            <div><span>PAYMENT ID</span><strong>{result.payment?.payment_id || result.payment_id || 'Not available'}</strong></div>
            <div><span>ORDER ID</span><strong>{result.order_id || 'Not available'}</strong></div>
            <div><span>AMOUNT</span><strong>{result.amount || booking?.total || '—'}</strong></div>
            <div><span>METHOD</span><strong>{displayMethod(result.payment?.method || result.method)}</strong></div>
            <div><span>STATUS</span><strong>{result.payment?.status || result.status || 'Not confirmed'}</strong></div>
            <div><span>TIME (IST)</span><strong>{formatDateTime(result.payment?.created_at || result.payment?.paid_at)}</strong></div>
          </div>
          {result.receipt?.receipt_number && <p className="cp-receipt">Receipt reference <strong>{result.receipt.receipt_number}</strong></p>}
          {error && <p className="cp-inline-error" role="alert">{error}</p>}
          {pending && !needsAttention && <button className="cp-pay-button" disabled={busy} onClick={() => recheck(result.order_id, result.payment?.payment_id || pendingOrder?.payment_id || '')}>{busy ? 'Checking same order…' : 'Retry verification'} <span>↻</span></button>}
          {failed && <button className="cp-pay-button" onClick={() => { setResult(null); setError(''); }}>Return to checkout <span>→</span></button>}
          {needsAttention && <p className="cp-attention-note">Keep the Order ID and Payment ID above for reconciliation. This page will not offer another payment.</p>}
          {successful && <p className="cp-confirm-note">Your confirmation is stored with the shared booking database.</p>}
        </div>
      </main>
    );
  }

  if (!booking) {
    return <main className="cp-shell"><section className="cp-error-card"><h1>Booking unavailable</h1><p>{error || 'Return to seat selection and open checkout from a valid pending booking.'}</p></section></main>;
  }

  return (
    <main className="cp-shell">
      <div className="cp-topbar"><div className="cp-brand"><span className="cp-brand-mark">c</span><span>cinepass<span>.</span></span></div><div className="cp-secure-pill"><i /> Secure checkout</div></div>
      <div className="cp-progress"><span>01&nbsp; Seat selection</span><b>02&nbsp; Payment</b><span>03&nbsp; Confirmation</span></div>
      <header className="cp-heading"><p className="cp-eyebrow">ALMOST MOVIE TIME</p><h1>Confirm your booking<span>.</span></h1><p>One final step before the show. Review your details, then continue to secure payment.</p></header>
      <div className="cp-checkout-grid">
        <section className="cp-card cp-show-card">
          <div className="cp-card-heading"><div><span className="cp-section-kicker">01 / YOUR EXPERIENCE</span><h2>Show details</h2></div><span className="cp-seat-pill"><i /> Seats selected</span></div>
          <div className="cp-art-row">
            {booking.poster_url ? <img className="cp-poster" src={booking.poster_url} alt={`${booking.event_title} poster`} /> : <div className="cp-poster cp-poster-fallback"><span>CP</span><small>YOUR NEXT<br/>FAVOURITE SCENE</small></div>}
            <div className="cp-show-copy"><p className="cp-type-tag">{String(booking.event_type || 'SHOW').toUpperCase()}</p><h3>{booking.event_title}</h3><p className="cp-venue">{booking.venue}{booking.city ? ` · ${booking.city}` : ''}{booking.screen ? ` · ${booking.screen}` : ''}</p>
              <div className="cp-detail-grid"><div><span>DATE</span><strong>{displayDate(booking.show_date)}</strong></div><div><span>SHOWTIME</span><strong>{displayTime(booking.show_date)}</strong></div><div><span>SELECTED SEATS</span><strong>{booking.seats?.join(', ') || '—'}</strong></div><div><span>BOOKING REF</span><strong>{booking.booking_number || booking.booking_id}</strong></div></div>
            </div>
          </div>
        </section>
        <aside className="cp-card cp-payment-card">
          <div className="cp-card-heading"><div><span className="cp-section-kicker">02 / PAYMENT</span><h2>Order summary</h2></div><span className="cp-lock">⌑ Secure</span></div>
          <div className="cp-summary-row"><div><span>Booking total</span><small>Calculated from your saved booking</small></div><strong>{booking.total || '—'}</strong></div>
          <div className="cp-total-row"><div><span>Total payable</span><small>INR · Razorpay Checkout</small></div><strong>{booking.total || '—'}</strong></div>
          <button className="cp-pay-button" onClick={beginPayment} disabled={busy || booking.status === 'confirmed' || Boolean(pendingOrder?.order_id)}>{busy ? 'Connecting securely…' : pendingOrder?.order_id ? 'Checking existing payment…' : booking.status === 'confirmed' ? 'Booking already paid' : `Pay ${booking.total || ''}`} <span>→</span></button>
          <p className="cp-payment-footnote"><span>✦</span> Select UPI, cards or another supported method inside Razorpay Checkout. Your payment details are never entered into Cinepass.</p>
          {error && <p className="cp-inline-error" role="alert">{error}</p>}
        </aside>
      </div>
      <footer className="cp-footer"><span>© Cinepass</span><span>Made for the movies <b>✦</b></span><span>Secure payment flow</span></footer>
    </main>
  );
}
