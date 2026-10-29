/**
 * ExpiredScreen.jsx — Phase 7 UX
 * ================================
 * Shown when user tries to pay but the seat lock has expired.
 * Clear message, greys out the expired seats, drops user back to seat map.
 */

export function ExpiredScreen({ expiredSeatIds, onRetry }) {
  return (
    <div className="expired-screen">
      <span className="expired-icon">⌛</span>
      <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 8 }}>
        Your hold has expired
      </h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.7 }}>
        The 5-minute hold on your selected seats has expired.
        Someone else may have grabbed them — please go back and
        re-select available seats.
      </p>

      {expiredSeatIds && expiredSeatIds.length > 0 && (
        <div style={{
          background: 'rgba(245,158,11,0.1)',
          border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: 12,
          padding: '12px 16px',
          marginBottom: 24,
          fontSize: 13,
        }}>
          <strong className="text-warning">Expired seats:</strong>{' '}
          <span className="text-secondary">{expiredSeatIds.join(', ')}</span>
        </div>
      )}

      <button id="btn-retry-selection" className="btn btn-primary" onClick={onRetry}>
        🔄 Choose seats again
      </button>
    </div>
  );
}
