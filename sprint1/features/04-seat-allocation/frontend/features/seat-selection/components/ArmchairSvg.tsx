import React from 'react';
import { SeatStatus, SeatType } from '../types/seat';

interface ArmchairSvgProps {
  status: SeatStatus;
  seatType: SeatType;
  isSelected: boolean;
  className?: string;
}

export const ArmchairSvg: React.FC<ArmchairSvgProps> = ({
  status,
  seatType,
  isSelected,
  className = 'w-7 h-7',
}) => {
  // Determine fill, stroke, and visual pattern according to state
  let fill = '#1F2937';
  let stroke = '#374151';
  let patternId: string | undefined;

  if (isSelected) {
    fill = '#3B82F6';
    stroke = '#60A5FA';
  } else if (status === 'available') {
    fill = '#10B981';
    stroke = '#34D399';
  } else if (status === 'locked') {
    fill = '#F59E0B';
    stroke = '#FBBF24';
  } else if (status === 'booked') {
    fill = '#374151';
    stroke = '#4B5563';
  } else if (status === 'reserved') {
    fill = 'url(#hatched-fill)';
    stroke = '#475569';
    patternId = 'hatched-fill';
  }

  const isAccessible = seatType === 'accessible';

  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {patternId && (
          <pattern id="hatched-fill" width="6" height="6" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#475569" strokeWidth="2.5" />
          </pattern>
        )}
      </defs>

      {/* Main Seat Backrest */}
      <rect
        x="6"
        y="4"
        width="20"
        height="14"
        rx="4"
        fill={fill}
        stroke={stroke}
        strokeWidth="1.5"
      />

      {/* Armrests (Left & Right) */}
      <rect
        x="3"
        y="12"
        width="4"
        height="12"
        rx="2"
        fill={fill}
        stroke={stroke}
        strokeWidth="1.5"
      />
      <rect
        x="25"
        y="12"
        width="4"
        height="12"
        rx="2"
        fill={fill}
        stroke={stroke}
        strokeWidth="1.5"
      />

      {/* Seat Cushion Bottom */}
      <rect
        x="6"
        y="15"
        width="20"
        height="10"
        rx="3"
        fill={fill}
        stroke={stroke}
        strokeWidth="1.5"
      />

      {/* Wheelchair Symbol for Accessible Seating */}
      {isAccessible && (
        <g transform="translate(10, 8) scale(0.55)" fill="currentColor" className="text-white drop-shadow">
          <circle cx="11" cy="4" r="2.5" />
          <path d="M19 13.5v-3c0-.83-.67-1.5-1.5-1.5h-5.22l-.46-2.31C11.66 5.86 10.93 5.3 10.1 5.3H6v2h3.42l1.62 8.12c.16.8.84 1.38 1.66 1.38H17v-2h-3.83l-.4-2H17.5c.83 0 1.5-.67 1.5-1.5z" />
          <path d="M10.5 16.5c-2.48 0-4.5 2.02-4.5 4.5s2.02 4.5 4.5 4.5 4.5-2.02 4.5-4.5h-2c0 1.38-1.12 2.5-2.5 2.5s-2.5-1.12-2.5-2.5 1.12-2.5 2.5-2.5v-2z" />
        </g>
      )}
    </svg>
  );
};
