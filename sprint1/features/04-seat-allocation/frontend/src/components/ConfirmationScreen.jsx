/**
 * ConfirmationScreen.jsx — Phase 5 / Phase 7
 * ============================================
 * Shown after successful booking confirmation.
 * Displays booking ID, seat list, and lets user navigate to bookings.
 */

export function ConfirmationScreen({ booking, onViewBookings, onBookAgain }) {
  return (
    <div className="confirmation-screen">
      <div className="confirmation-icon">✅</div>
      <h1 className="confirmation-title">Booking Confirmed!</h1>
      <p className="confirmation-subtitle">
        Your seats are secured. Enjoy the show! 🎉
      </p>

      <div className="booking-card">
        <div className="booking-id">Booking ID: {booking.booking_id}</div>

        <div style={{ marginBottom: 12 }}>
          <div className="text-xs text-muted" style={{ marginBottom: 4 }}>Seats booked</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {booking.seat_ids.map(id => (
              <span
                key={id}
                style={{
                  padding: '4px 10px',
                  background: 'rgba(139,92,246,0.15)',
                  border: '1px solid rgba(139,92,246,0.3)',
                  borderRadius: 20,
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--brand-400)',
                }}
              >
                {id}
              </span>
            ))}
          </div>
        </div>

        <div className="price-divider" />
        <div className="price-total">
          <span className="text-secondary text-sm">Total Paid</span>
          <span>₹{booking.total_price.toLocaleString('en-IN')}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button id="btn-view-bookings" className="btn btn-primary" onClick={onViewBookings}>
          📋 View My Bookings
        </button>
        <button id="btn-book-again" className="btn btn-secondary" onClick={onBookAgain}>
          🎟 Book Another Show
        </button>
      </div>
    </div>
  );
}
