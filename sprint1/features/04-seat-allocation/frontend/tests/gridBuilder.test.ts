import { describe, it, expect } from 'vitest';
import { buildSeatGrid, compareRowLabels } from '../features/seat-selection/utils/gridBuilder';
import { SeatItem } from '../features/seat-selection/types/seat';

describe('gridBuilder', () => {
  it('correctly compares row labels in natural cinema order', () => {
    expect(compareRowLabels('A', 'B')).toBeLessThan(0);
    expect(compareRowLabels('B', 'A')).toBeGreaterThan(0);
    expect(compareRowLabels('Z', 'AA')).toBeLessThan(0); // Single letter before double letter
    expect(compareRowLabels('AA', 'AB')).toBeLessThan(0);
  });

  it('inserts aisle spacers when seat numbers have gaps', () => {
    const mockSeats: SeatItem[] = [
      { show_seat_id: 's1', row_label: 'A', seat_number: 1, seat_type: 'standard', price: 200, status: 'available', is_mine: false },
      { show_seat_id: 's2', row_label: 'A', seat_number: 2, seat_type: 'standard', price: 200, status: 'available', is_mine: false },
      // Gap at seat_number 3 (Aisle)
      { show_seat_id: 's4', row_label: 'A', seat_number: 4, seat_type: 'standard', price: 200, status: 'available', is_mine: false },
    ];

    const bands = buildSeatGrid(mockSeats);
    expect(bands.length).toBe(1);
    const rowA = bands[0].rows[0];
    expect(rowA.seats.length).toBe(4);

    expect(rowA.seats[0].is_aisle).toBe(false);
    expect(rowA.seats[1].is_aisle).toBe(false);
    expect(rowA.seats[2].is_aisle).toBe(true); // Gap 3 is aisle
    expect(rowA.seats[3].is_aisle).toBe(false);
  });

  it('groups contiguous rows of identical type and price into bands', () => {
    const mockSeats: SeatItem[] = [
      { show_seat_id: 's1', row_label: 'A', seat_number: 1, seat_type: 'premium', price: 500, status: 'available', is_mine: false },
      { show_seat_id: 's2', row_label: 'B', seat_number: 1, seat_type: 'premium', price: 500, status: 'available', is_mine: false },
      { show_seat_id: 's3', row_label: 'C', seat_number: 1, seat_type: 'standard', price: 250, status: 'available', is_mine: false },
    ];

    const bands = buildSeatGrid(mockSeats);
    expect(bands.length).toBe(2);

    expect(bands[0].seat_type).toBe('premium');
    expect(bands[0].price).toBe(500);
    expect(bands[0].rows.length).toBe(2); // Rows A and B

    expect(bands[1].seat_type).toBe('standard');
    expect(bands[1].price).toBe(250);
    expect(bands[1].rows.length).toBe(1); // Row C
  });

  it('handles empty seat array gracefully without throwing', () => {
    const bands = buildSeatGrid([]);
    expect(bands).toEqual([]);
  });
});
