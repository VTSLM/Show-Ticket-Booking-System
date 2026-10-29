/**
 * Sidebar.jsx — Checkout Sidebar
 * ================================
 * Shows selected seats, running price total, lock countdown,
 * and the Proceed to Payment / Cancel buttons.
 */

import { useCountdown } from '../hooks/useCountdown';

const CONVENIENCE_FEE_RATE = 0.02; // 2%

function CountdownTimer({ expiresAt, onExpired }) {
  const { formatted, isExpired, isWarning } = useCountdown(expiresAt);

  // Notify parent when timer hits zero
  if (isExpired && onExpired) {
    onExpired();
  }

  if (!formatted) return null;

  return (
    <div className="countdown-wrapper">
      <span className="countdown-icon">⏱</span>
      <div>
        <div className="countdown-label">Hold expires in</div>
        <div className={`countdown-time ${isWarning ? 'warning' : ''}`}>{formatted}</div>
      </div>
    </div>
  );
}

export function CheckoutSidebar({
  selectedSeats,
  maxSeats,
  lockInfo,
  onRemoveSeat,
  onProceed,
  onCancelSelection,
  onLockExpired,
  isLocking,
  wsStatus,
}) {
  const subtotal = selectedSeats.reduce((sum, s) => sum + s.price, 0);
  const convenienceFee = Math.round(subtotal * CONVENIENCE_FEE_RATE);
  const total = subtotal + convenienceFee;

  const isLocked = !!lockInfo;
  const canProceed = selectedSeats.length > 0;

  return (
    <div className="checkout-sidebar">
      {/* WebSocket status indicator */}
      <div className={`ws-status ws-${wsStatus}`}>
        <span className="ws-dot" />
        {wsStatus === 'connected' && 'Live seat updates active'}
        {wsStatus === 'connecting' && 'Connecting to live updates...'}
        {wsStatus === 'disconnected' && 'Reconnecting...'}
      </div>

      {/* Lock countdown (only shown after hold is placed) */}
      {lockInfo && (
        <CountdownTimer
          expiresAt={lockInfo.expires_at}
          onExpired={onLockExpired}
        />
      )}

      {/* Selected seats card */}
      <div className="sidebar-card">
        <div className="sidebar-title">
          Selected Seats
          <span style={{
            fontSize: 12,
            fontWeight: 400,
            color: 'var(--text-muted)',
            marginLeft: 8,
          }}>
            {selectedSeats.length}/{maxSeats} max
          </span>
        </div>

        {selectedSeats.length === 0 ? (
          <div className="empty-selection">
            <span className="empty-icon">🪑</span>
            Click any green seat to select it
          </div>
        ) : (
          <div className="selected-seats-list">
            {selectedSeats.map(seat => (
              <div className="seat-item" key={seat.id}>
                <div>
                  <div className="seat-item-id">{seat.id}</div>
                  <div className="seat-item-section">{seat.section}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="seat-item-price">₹{seat.price.toLocaleString('en-IN')}</span>
                  {!isLocked && (
                    <button
                      className="seat-item-remove"
                      onClick={() => onRemoveSeat(seat.id)}
                      aria-label={`Remove ${seat.id}`}
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {selectedSeats.length > 0 && (
          <div>
            <div className="price-divider" />
            <div className="price-row">
              <span>Subtotal ({selectedSeats.length} seats)</span>
              <span>₹{subtotal.toLocaleString('en-IN')}</span>
            </div>
            <div className="price-row">
              <span>Convenience fee (2%)</span>
              <span>₹{convenienceFee.toLocaleString('en-IN')}</span>
            </div>
            <div className="price-divider" />
            <div className="price-total">
              <span>Total</span>
              <span>₹{total.toLocaleString('en-IN')}</span>
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      {!isLocked ? (
        <>
          <button
            id="btn-proceed-hold"
            className="btn btn-primary"
            disabled={!canProceed || isLocking}
            onClick={onProceed}
          >
            {isLocking ? (
              <>
                <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                Holding seats...
              </>
            ) : (
              <>🔒 Hold Seats & Continue</>
            )}
          </button>
          {canProceed && (
            <button
              className="btn btn-secondary"
              onClick={onCancelSelection}
            >
              Clear selection
            </button>
          )}
        </>
      ) : (
        <button
          className="btn btn-danger"
          onClick={onCancelSelection}
        >
          ✕ Release seats
        </button>
      )}

      {/* Info note */}
      <p className="text-xs text-muted" style={{ textAlign: 'center', paddingBottom: 4 }}>
        🔒 Seats are held for 5 minutes after confirming your selection.
        <br />No charges until payment is complete.
      </p>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
