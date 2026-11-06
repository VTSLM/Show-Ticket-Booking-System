/**
 * SeatMap.jsx — Phase 2 + Phase 6
 * ================================
 * Renders the interactive seat grid from seat data.
 *
 * Responsibilities:
 * - Group seats by section → row for 2D grid rendering
 * - Color-code by status: available, selected, locked, booked, blocked
 * - Click to select/deselect (enforces MAX_SEATS cap)
 * - Receive real-time updates via onStatusUpdate (from WebSocket)
 * - Show tooltips on hover
 */

import { useMemo } from 'react';

const SECTION_ORDER = ['VIP', 'PREMIUM', 'GENERAL'];

const SECTION_LABELS = {
  VIP: '⭐ VIP',
  PREMIUM: '💎 Premium',
  GENERAL: '🎟 General',
};

const SECTION_CLASS = {
  VIP: 'section-vip',
  PREMIUM: 'section-premium',
  GENERAL: 'section-general',
};

function getSeatClass(seat, isSelected, currentUserId) {
  if (isSelected) return 'seat-selected';
  switch (seat.status) {
    case 'available': return 'seat-available';
    case 'locked':    return 'seat-locked';
    case 'booked':    return 'seat-booked';
    case 'blocked':   return 'seat-blocked';
    default:          return 'seat-available';
  }
}

function SeatTooltip({ seat, isSelected }) {
  const status = isSelected
    ? 'Selected'
    : seat.status === 'locked'
    ? 'Held by someone'
    : seat.status.charAt(0).toUpperCase() + seat.status.slice(1);

  return (
    <div className="seat-tooltip">
      <strong>{seat.id}</strong> · ₹{seat.price.toLocaleString('en-IN')} · {status}
    </div>
  );
}

function Seat({ seat, isSelected, onToggle, maxReached }) {
  const isInteractive = seat.status === 'available' || isSelected;
  const canClick = isInteractive && (!maxReached || isSelected);

  const handleClick = () => {
    if (!canClick) return;
    onToggle(seat);
  };

  return (
    <div className="seat-wrapper">
      <button
        id={`seat-${seat.id}`}
        className={`seat ${getSeatClass(seat, isSelected)}`}
        onClick={handleClick}
        disabled={!canClick && seat.status !== 'available'}
        aria-label={`Seat ${seat.id}, ${seat.section}, ₹${seat.price}, ${isSelected ? 'selected' : seat.status}`}
        aria-pressed={isSelected}
        style={{
          cursor: canClick ? 'pointer' : 'not-allowed',
          opacity: (!canClick && seat.status === 'available' && !isSelected) ? 0.5 : undefined,
        }}
        title={seat.status === 'locked' ? 'Being held by another user' : undefined}
      >
        {seat.number}
      </button>
      <SeatTooltip seat={seat} isSelected={isSelected} />
    </div>
  );
}

export function SeatMap({ seats, selectedIds, onToggle, maxSeats, loading }) {
  // Group: section → row → seats[]
  const grouped = useMemo(() => {
    const map = {};
    for (const seat of seats) {
      if (!map[seat.section]) map[seat.section] = {};
      if (!map[seat.section][seat.row]) map[seat.section][seat.row] = [];
      map[seat.section][seat.row].push(seat);
    }
    // Sort seats within each row by number
    for (const section of Object.values(map)) {
      for (const row of Object.values(section)) {
        row.sort((a, b) => a.number - b.number);
      }
    }
    return map;
  }, [seats]);

  const maxReached = selectedIds.size >= maxSeats;

  // Section price (min price in section)
  const sectionPrice = useMemo(() => {
    const prices = {};
    for (const seat of seats) {
      if (!prices[seat.section] || seat.price < prices[seat.section]) {
        prices[seat.section] = seat.price;
      }
    }
    return prices;
  }, [seats]);

  if (loading) {
    return (
      <div className="loading-seats">
        {[1,2,3].map(i => (
          <div key={i} className="loading-row">
            <div className="skeleton" style={{ width: 28, height: 20, flexShrink: 0 }} />
            {Array.from({ length: 6 }).map((_, j) => (
              <div key={j} className="skeleton" style={{ width: 38, height: 38, borderRadius: 8 }} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Legend */}
      <div className="legend">
        <div className="legend-item">
          <div className="legend-seat" style={{ background: 'linear-gradient(145deg, #059669, #047857)' }} />
          Available
        </div>
        <div className="legend-item">
          <div className="legend-seat" style={{ background: 'linear-gradient(145deg, #7c3aed, #6d28d9)', boxShadow: '0 0 0 2px #a78bfa' }} />
          Selected
        </div>
        <div className="legend-item">
          <div className="legend-seat" style={{ background: 'linear-gradient(145deg, #b45309, #92400e)' }} />
          Held by others
        </div>
        <div className="legend-item">
          <div className="legend-seat" style={{ background: 'linear-gradient(145deg, #374151, #1f2937)', opacity: 0.6 }} />
          Booked
        </div>
        <div className="legend-item">
          <div className="legend-seat" style={{ background: '#1f2937', opacity: 0.3 }} />
          Blocked
        </div>
      </div>

      {/* Stage */}
      <div className="stage">🎭 STAGE / SCREEN</div>

      {/* Sections */}
      {SECTION_ORDER.filter(s => grouped[s]).map(sectionKey => {
        const rows = grouped[sectionKey];
        const rowKeys = Object.keys(rows).sort();
        return (
          <div className="seat-section" key={sectionKey}>
            <div className={`section-header ${SECTION_CLASS[sectionKey]}`}>
              <span className="section-name">{SECTION_LABELS[sectionKey]}</span>
              <span className="section-price">from ₹{sectionPrice[sectionKey]?.toLocaleString('en-IN')}</span>
            </div>
            {rowKeys.map(rowKey => (
              <div className="seat-row" key={rowKey}>
                <span className="row-label">{rowKey}</span>
                <div className="seats-grid">
                  {rows[rowKey].map(seat => (
                    <Seat
                      key={seat.id}
                      seat={seat}
                      isSelected={selectedIds.has(seat.id)}
                      onToggle={onToggle}
                      maxReached={maxReached}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
