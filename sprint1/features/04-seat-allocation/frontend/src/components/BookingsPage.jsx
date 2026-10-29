/**
 * BookingsPage.jsx — User's booking history (FR: booking history dashboard)
 */

import { useState, useEffect } from 'react';
import { api } from '../api';

const DEMO_USER_ID = 'user-demo-khushi';

export function BookingsPage({ showToast }) {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getUserBookings(DEMO_USER_ID);
      setBookings(data.bookings || []);
    } catch (e) {
      showToast('Error', 'Could not load bookings.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCancel = async (bookingId) => {
    if (!window.confirm('Cancel this booking? Seats will be released.')) return;
    setCancellingId(bookingId);
    try {
      await api.cancelBooking(bookingId, DEMO_USER_ID);
      showToast('Booking cancelled', 'Your seats have been released.', 'success');
      load();
    } catch (e) {
      showToast('Cannot cancel', e.message, 'error');
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <div className="bookings-page">
      <h1 className="page-title">My Bookings</h1>

      {loading && (
        <div>
          {[1,2].map(i => (
            <div key={i} className="skeleton" style={{ height: 100, borderRadius: 16, marginBottom: 16 }} />
          ))}
        </div>
      )}

      {!loading && bookings.length === 0 && (
        <div className="empty-selection" style={{ padding: 48 }}>
          <span className="empty-icon" style={{ fontSize: 48 }}>🎟</span>
          <p style={{ fontSize: 16, color: 'var(--text-secondary)' }}>No bookings yet.</p>
          <p className="text-muted text-sm" style={{ marginTop: 4 }}>Book some seats and they'll appear here.</p>
        </div>
      )}

      {bookings.map(b => (
        <div className="booking-history-card" key={b.booking_id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div>
              <div className="booking-id">{b.booking_id}</div>
              <div className="text-xs text-muted" style={{ marginTop: 4 }}>
                {new Date(b.created_at).toLocaleString('en-IN', {
                  dateStyle: 'medium', timeStyle: 'short',
                })}
              </div>
            </div>
            <span className={`booking-status-badge status-${b.status}`}>
              {b.status}
            </span>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
            {b.seat_ids.map(id => (
              <span
                key={id}
                style={{
                  padding: '3px 8px',
                  background: 'rgba(139,92,246,0.1)',
                  border: '1px solid rgba(139,92,246,0.2)',
                  borderRadius: 20,
                  fontSize: 11,
                  color: 'var(--brand-400)',
                  fontWeight: 600,
                }}
              >
                {id}
              </span>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 16, fontWeight: 700 }}>
              ₹{b.total_price.toLocaleString('en-IN')}
            </span>
            {b.status === 'confirmed' && (
              <button
                className="btn btn-danger btn-sm"
                style={{ width: 'auto' }}
                onClick={() => handleCancel(b.booking_id)}
                disabled={cancellingId === b.booking_id}
              >
                {cancellingId === b.booking_id ? 'Cancelling...' : 'Cancel Booking'}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
