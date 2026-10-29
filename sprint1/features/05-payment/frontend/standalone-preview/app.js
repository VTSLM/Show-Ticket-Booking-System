const params = new URLSearchParams(window.location.search);
const recoveryOrderId = params.get('reconcile_order_id') || '';
const recoveryPaymentId = params.get('payment_id') || '';
const PENDING_VERIFICATION_KEY = 'cinepass.pendingRazorpayVerification';
function readPendingVerification() {
  try { return JSON.parse(sessionStorage.getItem(PENDING_VERIFICATION_KEY) || 'null'); }
  catch { return null; }
}
let pendingReconciliation = readPendingVerification();
let bookingId = params.get('booking_id') || pendingReconciliation?.booking_id || '';
let resumeExistingBooking = Boolean(params.get('booking_id') || pendingReconciliation?.booking_id);
let booking = null;
let currentOrder = null;
let toastTimer;
let externalCheckoutOpen = false;
let verifyingRazorpayPayment = false;
let handlingProviderFailure = false;
const methodLabels = {
  upi: 'UPI', card: 'Card', netbanking: 'Net banking', wallet: 'Wallet',
  paylater: 'Pay later', emi: 'EMI', app: 'App'
};
const $ = (id) => document.getElementById(id);

function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove('show'), 3200);
}

function persistPendingVerification(orderId, paymentId = '', associatedBookingId = bookingId) {
  if (!orderId) return;
  pendingReconciliation = {
    order_id: orderId,
    payment_id: paymentId || '',
    booking_id: associatedBookingId || '',
  };
  try { sessionStorage.setItem(PENDING_VERIFICATION_KEY, JSON.stringify(pendingReconciliation)); } catch { /* Session storage is optional. */ }
}

function clearPendingVerification() {
  pendingReconciliation = null;
  try { sessionStorage.removeItem(PENDING_VERIFICATION_KEY); } catch { /* Session storage is optional. */ }
  const url = new URL(window.location.href);
  url.searchParams.delete('reconcile_order_id');
  url.searchParams.delete('payment_id');
  if (url.href !== window.location.href) window.history.replaceState({}, '', url);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function paintBooking(data) {
  booking = data;
  $('movie-title').textContent = data.event_title || 'Your show';
  $('order-movie-title').textContent = data.event_title || 'Your show';
  $('order-show-line').textContent = `${data.venue || 'Venue'} · ${data.city || ''}`.trim();
  $('order-seat-label').textContent = (data.seats || []).join(', ') || '—';
  $('order-ticket-count').textContent = `${String(data.ticket_count || 0).padStart(2, '0')} ${(data.ticket_count || 0) === 1 ? 'ticket' : 'tickets'}`;
  $('ticket-price-subtitle').textContent = `${data.ticket_count || 0} ${(data.ticket_count || 0) === 1 ? 'ticket' : 'tickets'}`;
  $('movie-venue').textContent = `${data.venue || 'Venue'}${data.city ? `, ${data.city}` : ''}`;
  $('movie-date').textContent = displayDate(data.show_date);
  $('movie-time').textContent = data.show_time || '—';
  $('movie-seats').textContent = (data.seats || []).join(', ') || '—';
  $('booking-number').textContent = data.booking_number || '—';
  $('ticket-count').textContent = `${data.ticket_count || 0} ${(data.ticket_count || 0) === 1 ? 'seat' : 'seats'}`;
  $('subtotal').textContent = data.subtotal || '—';
  $('fee').textContent = data.convenience_fee || '₹0.00';
  $('tax').textContent = data.tax || '₹0.00';
  $('total').textContent = data.total || '—';
  $('pay-label').textContent = `Pay ${data.total || ''}`;
  if (data.status === 'confirmed') {
    $('pay-button').disabled = true;
    $('pay-label').textContent = 'Booking already paid';
  }
}

function displayDate(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' }).format(parsed);
  }
  return String(value).replace(/^[A-Za-z]+,?\s*/, '');
}

function formatTimestamp(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(parsed) + ' IST';
}

function humanStatus(status) {
  const normal = String(status || 'not_confirmed').toLowerCase();
  if (normal === 'successful' || normal === 'captured') return 'Successful';
  if (normal === 'failed') return 'Failed';
  if (normal === 'cancelled') return 'Cancelled';
  if (normal === 'authorized') return 'Authorized — not confirmed';
  if (normal === 'processing' || normal === 'verification_pending' || normal === 'created') return 'Verification pending';
  return 'Not confirmed';
}

function humanMethod(method) {
  if (!method) return 'Not available';
  const normalized = String(method).toLowerCase();
  if (normalized === 'checkout' || normalized === 'unknown') return 'Not available yet';
  return methodLabels[normalized] || normalized.replace(/[_-]/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function resetCheckoutButton() {
  const confirmed = booking?.status === 'confirmed';
  $('pay-button').disabled = confirmed;
  $('pay-label').textContent = confirmed ? 'Booking already paid' : `Pay ${booking?.total || ''}`;
}

function showProcessing(order, checkingOrder = false) {
  $('checkout-view').classList.add('hidden');
  $('result-view').classList.remove('hidden');
  $('result-view').classList.add('is-visible');
  $('result-card').className = 'result-card state-processing';
  $('result-animation').className = 'result-animation';
  $('result-animation').classList.add('state-processing');
  $('result-symbol').textContent = '↻';
  $('result-eyebrow').textContent = '03 / VERIFICATION';
  $('result-title').textContent = checkingOrder ? 'Checking payment status' : 'Verifying your payment';
  $('result-message').textContent = checkingOrder
    ? 'We are checking the existing checkout order for any payment attempt. Do not start another payment while this check is in progress.'
    : 'We are verifying the payment reference and checking its final status securely.';
  $('result-status-chip').textContent = 'VERIFYING';
  $('result-status-chip').className = 'status-chip processing';
  $('result-status-copy').textContent = 'Please keep this page open';
  fillResultDetails({
    order_id: order?.order_id,
    amount: booking?.total,
    status: 'processing',
    method: null,
    timestamp: 'Not available yet',
  });
  $('result-actions').classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showPaymentResult(result, messageOverride = '') {
  const payment = result.payment || {};
  const status = String(payment.status || result.status || 'not_confirmed').toLowerCase();
  const successful = status === 'successful' || status === 'captured';
  const cancelled = status === 'cancelled';
  const pending = ['verification_pending', 'processing', 'created', 'authorized'].includes(status);
  const state = successful ? 'success' : pending ? 'processing' : 'failure';
  const title = successful
    ? 'Payment confirmed'
    : pending
      ? (status === 'authorized' ? 'Payment authorized — awaiting confirmation' : ((payment.payment_id || result.payment_id || pendingReconciliation?.payment_id) ? 'Payment received — verifying' : 'Checking payment status'))
      : cancelled ? 'Payment cancelled' : 'Payment failed';
  const noPaymentAttempt = cancelled && !payment.payment_id && !result.payment_id;
  const message = messageOverride || (successful
    ? 'Your payment has been verified by Razorpay. Your booking is confirmed.'
    : pending
      ? 'We could not confirm the final payment status yet. Do not pay again. Check this same order again to reconcile the existing transaction.'
      : noPaymentAttempt
        ? 'No payment attempt was found for this order. Your booking remains unpaid, and the order check is complete. You can return to checkout when ready.'
        : cancelled ? 'Checkout was cancelled before payment was confirmed. No booking confirmation was issued.'
          : 'The payment provider reported that this payment failed. Your booking has not been confirmed. You can retry after this failure has been verified.');

  $('checkout-view').classList.add('hidden');
  $('result-view').classList.remove('hidden');
  $('result-view').classList.remove('is-visible');
  $('result-card').className = `result-card state-${state}`;
  $('result-animation').className = `result-animation state-${state}`;
  $('result-symbol').textContent = successful ? '✓' : pending ? '↻' : cancelled ? '↶' : '×';
  $('result-eyebrow').textContent = pending ? '03 / VERIFICATION' : '03 / PAYMENT RESULT';
  $('result-title').textContent = title;
  $('result-message').textContent = message;
  $('result-status-chip').textContent = (pending ? 'VERIFYING' : humanStatus(status)).toUpperCase();
  $('result-status-chip').className = `status-chip ${successful ? 'successful' : pending ? 'processing' : cancelled ? 'cancelled' : 'failed'}`;
  $('result-status-copy').textContent = successful
    ? 'Verified by Razorpay'
    : pending
      ? ((payment.payment_id || result.payment_id || pendingReconciliation?.payment_id)
        ? 'Do not start another payment while this one is being checked'
        : 'Checking this order for a payment attempt')
      : 'Booking not confirmed';
  fillResultDetails({
    order_id: result.order_id || currentOrder?.order_id || '—',
    payment_id: payment.payment_id || result.payment_id || pendingReconciliation?.payment_id || 'Not available',
    amount: result.amount || booking?.total || '—',
    status: humanStatus(status),
    method: humanMethod(payment.method || result.method),
    timestamp: (payment.created_at || payment.paid_at || result.payment_timestamp)
      ? formatTimestamp(payment.created_at || payment.paid_at || result.payment_timestamp)
      : 'Not available',
  });

  const actions = $('result-actions');
  actions.classList.toggle('hidden', successful);
  $('retry-payment').textContent = pending
    ? ((payment.payment_id || result.payment_id || pendingReconciliation?.payment_id) ? 'Retry verification' : 'Check payment status')
    : noPaymentAttempt ? 'Return to checkout' : 'Try payment again';
  $('retry-payment').disabled = false;
  if (successful) {
    clearPendingVerification();
    if (result.booking) booking = result.booking;
  } else if (pending) {
    persistPendingVerification(result.order_id || currentOrder?.order_id, payment.payment_id || result.payment_id || pendingReconciliation?.payment_id || '', result.booking_id || bookingId);
  } else {
    clearPendingVerification();
  }
  $('result-view').classList.add('is-visible');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function fillResultDetails(data) {
  $('result-payment-id').textContent = data.payment_id || 'Not available';
  $('result-order-id').textContent = data.order_id || '—';
  $('result-amount').textContent = data.amount || '—';
  $('result-status').textContent = data.status || 'Not confirmed';
  $('result-method').textContent = data.method || 'Not available';
  $('result-timestamp').textContent = data.timestamp || '—';
}

function showVerificationError(error, paymentId = '', orderId = '') {
  const selectedOrderId = orderId || currentOrder?.order_id || pendingReconciliation?.order_id;
  const selectedPaymentId = paymentId || pendingReconciliation?.payment_id;
  if (selectedOrderId) {
    persistPendingVerification(selectedOrderId, selectedPaymentId || '', bookingId);
  }
  showPaymentResult({
    provider: 'razorpay',
    order_id: selectedOrderId || '—',
    booking_id: bookingId,
    amount: booking?.total || '—',
    status: 'verification_pending',
    payment: { payment_id: selectedPaymentId || '', status: 'verification_pending' },
  }, 'We could not verify this order with the payment provider. Do not start another payment yet. Check this same order again to reconcile the existing transaction.');
}

async function retryVerification() {
  const orderId = pendingReconciliation?.order_id || currentOrder?.order_id;
  const paymentId = pendingReconciliation?.payment_id || '';
  if (!orderId) {
    toast('This payment order cannot be recovered in this browser. Check the existing transaction before starting another payment.');
    return;
  }
  const button = $('retry-payment');
  button.disabled = true;
  button.textContent = 'Checking payment status…';
  try {
    const result = await api(`/api/payments/orders/${encodeURIComponent(orderId)}/recheck`, {
      method: 'POST',
      body: JSON.stringify(paymentId ? { payment_id: paymentId } : {}),
    });
    currentOrder = { order_id: orderId };
    showPaymentResult(result);
  } catch (error) {
    showVerificationError(error, paymentId, orderId);
  } finally {
    button.disabled = false;
  }
}

function openRazorpayCheckout(order) {
  if (typeof window.Razorpay !== 'function') {
    throw new Error('Razorpay Checkout could not load. Check your internet connection and reload this page.');
  }
  const options = {
    key: order.key_id,
    amount: order.amount_paise,
    currency: order.currency || 'INR',
    name: 'Cinepass',
    description: `${booking.event_title} · ${(booking.seats || []).join(', ')}`,
    order_id: order.order_id,
    notes: { booking_number: booking.booking_number },
    theme: { color: '#287cff' },
    handler: async function (response) {
      externalCheckoutOpen = false;
      verifyingRazorpayPayment = true;
      showProcessing(order);
      try {
        const result = await api(`/api/payments/orders/${encodeURIComponent(order.order_id)}/verify`, {
          method: 'POST',
          body: JSON.stringify(response),
        });
        showPaymentResult(result);
      } catch (error) {
        showVerificationError(error, response.razorpay_payment_id, order.order_id);
      } finally {
        verifyingRazorpayPayment = false;
        if (booking?.status !== 'confirmed') resetCheckoutButton();
      }
    },
    modal: {
      ondismiss: async function () {
        externalCheckoutOpen = false;
        if (!verifyingRazorpayPayment && !handlingProviderFailure) {
          // Closing Checkout is not proof that no payment happened. Reconcile this
          // exact order before making its Pay button available again.
          persistPendingVerification(order.order_id, '', bookingId);
          currentOrder = order;
          showProcessing(order, true);
          await retryVerification();
        }
      },
    },
  };
  const checkout = new window.Razorpay(options);
  checkout.on('payment.failed', async function (response) {
    externalCheckoutOpen = false;
    handlingProviderFailure = true;
    const error = response?.error || {};
    const metadata = error.metadata || {};
    const paymentId = metadata.payment_id || '';
    const orderId = metadata.order_id || currentOrder?.order_id || order.order_id;
    try { checkout.close(); } catch { /* Checkout may already have closed. */ }
    // A browser failure event is not the authoritative payment record. Query
    // Razorpay for this same order/payment before offering a new attempt.
    persistPendingVerification(orderId, paymentId, bookingId);
    currentOrder = { order_id: orderId };
    showProcessing(currentOrder);
    try {
      const result = await api(`/api/payments/orders/${encodeURIComponent(orderId)}/recheck`, {
        method: 'POST',
        body: JSON.stringify(paymentId ? { payment_id: paymentId } : {}),
      });
      showPaymentResult(result);
    } catch (recheckError) {
      showVerificationError(recheckError, paymentId, orderId);
    } finally {
      handlingProviderFailure = false;
      if (booking?.status !== 'confirmed') resetCheckoutButton();
    }
  });
  externalCheckoutOpen = true;
  checkout.open();
}

async function beginPayment() {
  if (!booking) return;
  if (booking.status === 'confirmed') { toast('This booking is already paid.'); return; }
  if (pendingReconciliation?.order_id) {
    currentOrder = { order_id: pendingReconciliation.order_id };
    $('checkout-view').classList.add('hidden');
    showProcessing(currentOrder, !pendingReconciliation.payment_id);
    await retryVerification();
    return;
  }
  $('pay-button').disabled = true;
  $('pay-label').textContent = 'Connecting to Razorpay…';
  try {
    const order = await api('/api/payments/orders', {
      method: 'POST',
      body: JSON.stringify({ booking_id: bookingId }),
    });
    if (order.provider !== 'razorpay') {
      throw new Error('Secure payment is temporarily unavailable. Please check the payment service configuration.');
    }
    currentOrder = order;
    // Keep the order reference so a refresh/closed Checkout is reconciled first.
    persistPendingVerification(order.order_id, '', bookingId);
    openRazorpayCheckout(order);
  } catch (error) {
    if (currentOrder?.order_id && pendingReconciliation?.order_id === currentOrder.order_id) {
      // If Checkout could not open, reconcile the created order before allowing
      // another attempt. A failed script load is not a provider payment result.
      showProcessing(currentOrder, true);
      await retryVerification();
    } else {
      const existingOrder = error.message.match(/existing payment order needs reconciliation:\s*([A-Za-z0-9_-]+)/i);
      if (existingOrder?.[1]) {
        // The backend may discover an earlier order after session storage was
        // cleared or unavailable. Resume reconciliation instead of opening a
        // second order or losing the recovery reference.
        currentOrder = { order_id: existingOrder[1] };
        persistPendingVerification(existingOrder[1], '', bookingId);
        showProcessing(currentOrder, true);
        await retryVerification();
      } else {
        toast(error.message);
        resetCheckoutButton();
      }
    }
  } finally {
    if (!externalCheckoutOpen && !verifyingRazorpayPayment && $('checkout-view').classList.contains('hidden') === false) resetCheckoutButton();
  }
}

$('pay-button').addEventListener('click', beginPayment);
$('retry-payment').addEventListener('click', async () => {
  if (pendingReconciliation?.order_id) {
    await retryVerification();
    return;
  }
  $('result-view').classList.remove('is-visible');
  $('result-view').classList.add('hidden');
  $('checkout-view').classList.remove('hidden');
  currentOrder = null;
  resetCheckoutButton();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

(async function init() {
  try {
    const health = await api('/api/health');
    if (health.provider !== 'razorpay') {
      toast('Secure payment is temporarily unavailable. Please check the payment service configuration.');
    }

    // A specific recovery URL can be used to reconcile a payment that was
    // successful at Razorpay but not saved locally after a previous API outage.
    if (recoveryOrderId && recoveryPaymentId) {
      currentOrder = { order_id: recoveryOrderId };
      const orderData = await api(`/api/payments/orders/${encodeURIComponent(recoveryOrderId)}`);
      bookingId = orderData.booking_id;
      paintBooking(orderData.booking);
      persistPendingVerification(recoveryOrderId, recoveryPaymentId, bookingId);
      try {
        const result = await api(`/api/payments/orders/${encodeURIComponent(recoveryOrderId)}/recheck`, {
          method: 'POST',
          body: JSON.stringify({ payment_id: recoveryPaymentId }),
        });
        showPaymentResult(result);
      } catch (error) {
        showVerificationError(error, recoveryPaymentId, recoveryOrderId);
      }
      return;
    }

    const data = resumeExistingBooking
      ? await api(`/api/payments/booking/${encodeURIComponent(bookingId)}`)
      : await api('/api/payments/bookings/demo', { method: 'POST' });
    bookingId = data.booking_id;
    paintBooking(data);

    if (pendingReconciliation && pendingReconciliation.order_id &&
        (!pendingReconciliation.booking_id || pendingReconciliation.booking_id === bookingId)) {
      currentOrder = { order_id: pendingReconciliation.order_id };
      try {
        const result = await api(`/api/payments/orders/${encodeURIComponent(pendingReconciliation.order_id)}/recheck`, {
          method: 'POST',
          body: JSON.stringify(pendingReconciliation.payment_id ? { payment_id: pendingReconciliation.payment_id } : {}),
        });
        showPaymentResult(result);
      } catch (error) {
        showVerificationError(error, pendingReconciliation.payment_id, pendingReconciliation.order_id);
      }
      return;
    }

    if (resumeExistingBooking && data.latest_payment?.payment?.status === 'successful') {
      currentOrder = { order_id: data.latest_payment.order_id };
      showPaymentResult(data.latest_payment);
    }
  } catch (error) {
    document.querySelector('.page-heading h1').textContent = 'Booking unavailable';
    document.querySelector('.subheading').textContent = error.message;
    $('pay-button').disabled = true;
    $('pay-label').textContent = 'Cannot continue';
  }
})();
