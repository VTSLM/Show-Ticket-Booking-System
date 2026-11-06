import React from 'react';
import { ArmchairSvg } from './ArmchairSvg';

export const SeatLegend: React.FC = () => {
  const items = [
    { label: 'Selected', status: 'available' as const, seatType: 'standard' as const, isSelected: true },
    { label: 'Available', status: 'available' as const, seatType: 'standard' as const, isSelected: false },
    { label: 'Taken', status: 'booked' as const, seatType: 'standard' as const, isSelected: false },
    { label: 'Held by others', status: 'locked' as const, seatType: 'standard' as const, isSelected: false },
    { label: 'Not for sale', status: 'reserved' as const, seatType: 'standard' as const, isSelected: false },
    { label: 'Accessible', status: 'available' as const, seatType: 'accessible' as const, isSelected: false },
  ];

  return (
    <div
      aria-label="Seat Map Legend"
      className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 py-4 px-6 bg-surface-card/60 border border-surface-border rounded-xl backdrop-blur-sm max-w-3xl mx-auto my-6"
    >
      {items.map((item) => (
        <div key={item.label} className="flex items-center space-x-2">
          <ArmchairSvg
            status={item.status}
            seatType={item.seatType}
            isSelected={item.isSelected}
            className="w-5 h-5 flex-shrink-0"
          />
          <span className="text-xs font-medium text-gray-300">{item.label}</span>
        </div>
      ))}
    </div>
  );
};
