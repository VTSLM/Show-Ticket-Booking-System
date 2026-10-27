import React, { useState } from 'react';
import clsx from 'clsx';
import { GridSeat, SeatItem } from '../types/seat';
import { ArmchairSvg } from './ArmchairSvg';
import { formatCurrency } from '../utils/formatters';

interface SeatButtonProps {
  seat: GridSeat;
  isSelected: boolean;
  onToggle: (seat: SeatItem) => void;
  tabIndex?: number;
}

export const SeatButton: React.FC<SeatButtonProps> = ({
  seat,
  isSelected,
  onToggle,
  tabIndex = 0,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  // Aisle spacer renders as an empty block keeping rows aligned
  if (seat.is_aisle) {
    return <div className="w-8 h-8 flex-shrink-0" aria-hidden="true" />;
  }

  const isClickable = seat.status === 'available' || seat.is_mine;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      if (isClickable) {
        onToggle(seat);
      }
    } else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
      e.preventDefault();
      const current = e.currentTarget;
      const allButtons = Array.from(
        document.querySelectorAll<HTMLButtonElement>('button[data-seat-btn="true"]')
      );
      const currentIndex = allButtons.indexOf(current);

      let targetIndex = currentIndex;
      if (e.key === 'ArrowRight') targetIndex = currentIndex + 1;
      else if (e.key === 'ArrowLeft') targetIndex = currentIndex - 1;
      else if (e.key === 'ArrowDown') targetIndex = currentIndex + 10; // Jump downward in grid
      else if (e.key === 'ArrowUp') targetIndex = currentIndex - 10;

      if (targetIndex >= 0 && targetIndex < allButtons.length) {
        allButtons[targetIndex]?.focus();
      }
    }
  };

  const statusDescription = isSelected
    ? 'Selected'
    : seat.status === 'locked'
    ? seat.is_mine
      ? 'Held by you'
      : 'Held by others'
    : seat.status === 'booked'
    ? 'Taken'
    : seat.status === 'reserved'
    ? 'Not for sale'
    : 'Available';

  const ariaLabel = `Row ${seat.row_label}, Seat ${seat.seat_number}, ${seat.seat_type}, ${formatCurrency(seat.price)}, ${statusDescription}`;
  const tooltipText = `Row ${seat.row_label} - Seat ${seat.seat_number} - ${seat.seat_type.toUpperCase()} - ${formatCurrency(seat.price)}`;

  return (
    <div
      className="relative flex items-center justify-center flex-shrink-0"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <button
        type="button"
        data-seat-btn="true"
        data-row={seat.row_label}
        data-num={seat.seat_number}
        tabIndex={tabIndex}
        aria-label={ariaLabel}
        aria-pressed={isSelected}
        disabled={!isClickable}
        onClick={() => {
          if (isClickable) {
            onToggle(seat);
          }
        }}
        onKeyDown={handleKeyDown}
        className={clsx(
          'p-0.5 rounded transition-transform duration-150 relative outline-none',
          'focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B0F19]',
          isClickable && 'hover:scale-110 cursor-pointer active:scale-95',
          !isClickable && 'cursor-not-allowed opacity-80'
        )}
      >
        <ArmchairSvg
          status={seat.status}
          seatType={seat.seat_type}
          isSelected={isSelected}
          className="w-7 h-7 sm:w-8 sm:h-8 drop-shadow"
        />
      </button>

      {/* Hover Floating Tooltip */}
      {showTooltip && (
        <div
          role="tooltip"
          className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap px-2.5 py-1 text-[11px] font-medium text-white bg-gray-900 border border-gray-700 rounded-md shadow-xl z-50 pointer-events-none"
        >
          {tooltipText}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  );
};
