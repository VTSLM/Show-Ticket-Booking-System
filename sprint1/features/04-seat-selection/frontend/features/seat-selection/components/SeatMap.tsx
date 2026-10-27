import React from 'react';
import { useSeatSelection } from '../context/SeatSelectionContext';
import { ScreenCurve } from './ScreenCurve';
import { SeatButton } from './SeatButton';
import { SeatLegend } from './SeatLegend';

export const SeatMap: React.FC = () => {
  const { bands, state, toggleSeat } = useSeatSelection();
  const selectedSet = new Set(state.selectedSeatIds);

  if (bands.length === 0) {
    return (
      <div className="w-full lg:w-[68%] bg-surface-card border border-surface-border rounded-2xl p-12 text-center">
        <h3 className="text-base font-semibold text-white mb-2">No Seats Configured</h3>
        <p className="text-sm text-gray-400">
          This auditorium does not currently have a seat layout configured for this show.
        </p>
      </div>
    );
  }

  // Discover global maximum column width for the bottom column indicator
  let maxCols = 0;
  bands.forEach((b) => {
    b.rows.forEach((r) => {
      if (r.seats.length > maxCols) maxCols = r.seats.length;
    });
  });

  return (
    <div
      aria-label="Interactive Seat Map"
      className="w-full lg:w-[68%] bg-surface-card border border-surface-border rounded-2xl p-6 sm:p-8 shadow-xl flex flex-col items-center"
    >
      {/* Illuminated Curved Cinema Screen */}
      <ScreenCurve />

      {/* Responsive Hall Container with Internal Horizontal Scroll */}
      <div className="w-full overflow-x-auto pb-6 scrollbar-thin flex flex-col items-center">
        <div className="inline-flex flex-col items-center min-w-max space-y-6 px-4">
          {bands.map((band, bandIdx) => (
            <section
              key={`${band.seat_type}-${band.price}-${bandIdx}`}
              aria-label={band.title}
              className="w-full flex flex-col items-center"
            >
              {/* Band Tier Header */}
              <div className="w-full flex items-center justify-center my-3">
                <div className="h-px bg-gradient-to-r from-transparent via-gray-700 to-transparent flex-grow max-w-xs" />
                <span className="px-3 text-[11px] font-bold uppercase tracking-widest text-gray-400">
                  {band.title}
                </span>
                <div className="h-px bg-gradient-to-r from-transparent via-gray-700 to-transparent flex-grow max-w-xs" />
              </div>

              {/* Rows inside Band */}
              <div className="space-y-2.5">
                {band.rows.map((row) => (
                  <div
                    key={row.row_label}
                    className="flex items-center space-x-3 sm:space-x-4"
                  >
                    {/* Left Row Label */}
                    <span
                      aria-hidden="true"
                      className="w-5 text-right font-bold text-xs text-gray-400 select-none"
                    >
                      {row.row_label}
                    </span>

                    {/* Seat Grid Row with Aligned Aisle Spacers */}
                    <div className="flex items-center space-x-1.5 sm:space-x-2">
                      {row.seats.map((seat) => (
                        <SeatButton
                          key={seat.show_seat_id}
                          seat={seat}
                          isSelected={selectedSet.has(seat.show_seat_id)}
                          onToggle={toggleSeat}
                        />
                      ))}
                    </div>

                    {/* Right Row Label */}
                    <span
                      aria-hidden="true"
                      className="w-5 text-left font-bold text-xs text-gray-400 select-none"
                    >
                      {row.row_label}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          ))}

          {/* Seat Numbers Along the Bottom */}
          <div className="pt-4 border-t border-gray-800/60 w-full flex justify-center">
            <div className="flex items-center space-x-1.5 sm:space-x-2 px-8">
              {Array.from({ length: maxCols }).map((_, idx) => (
                <div
                  key={idx}
                  className="w-7 sm:w-8 text-center text-[10px] font-medium text-gray-400 select-none"
                >
                  {idx + 1}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Accessible Legend */}
      <SeatLegend />
    </div>
  );
};
