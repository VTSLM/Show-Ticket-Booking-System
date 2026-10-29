import { describe, it, expect } from 'vitest';
import {
  seatSelectionReducer,
  createInitialState,
} from '../features/seat-selection/context/seatSelectionReducer';
import { SeatItem, SeatMapData } from '../features/seat-selection/types/seat';

describe('seatSelectionReducer', () => {
  const mockSeat: SeatItem = {
    show_seat_id: 'seat-1',
    row_label: 'A',
    seat_number: 1,
    seat_type: 'standard',
    price: 300,
    status: 'available',
    is_mine: false,
  };

  it('selects and deselects an available seat', () => {
    let state = createInitialState('show-123');

    // Select
    state = seatSelectionReducer(state, { type: 'TOGGLE_SEAT', payload: mockSeat });
    expect(state.selectedSeatIds).toEqual(['seat-1']);

    // Deselect
    state = seatSelectionReducer(state, { type: 'TOGGLE_SEAT', payload: mockSeat });
    expect(state.selectedSeatIds).toEqual([]);
  });

  it('enforces maximum seats limit without dropping silently', () => {
    let state = createInitialState('show-123');
    // Pre-populate 8 seats
    state = {
      ...state,
      mapData: {
        max_seats_per_booking: 8,
      } as SeatMapData,
      selectedSeatIds: ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8'],
    };

    // Attempt to select a 9th seat
    state = seatSelectionReducer(state, { type: 'TOGGLE_SEAT', payload: mockSeat });
    expect(state.selectedSeatIds.length).toBe(8);
    expect(state.toasts.length).toBe(1);
    expect(state.toasts[0].message).toContain('You can only select up to 8 seats');
  });

  it('deselects only failed seats on conflict without wiping others', () => {
    let state = createInitialState('show-123');
    state = {
      ...state,
      selectedSeatIds: ['seat-1', 'seat-2', 'seat-3'],
    };

    // Failed seat-2
    state = seatSelectionReducer(state, {
      type: 'DESELECT_SEATS',
      payload: ['seat-2'],
    });

    expect(state.selectedSeatIds).toEqual(['seat-1', 'seat-3']);
  });

  it('discards out-of-order stale poll responses based on sequence number', () => {
    let state = createInitialState('show-123');
    state = { ...state, pollSequence: 5 };

    const staleMapData: SeatMapData = {
      server_time: '2026-10-27T10:00:00Z',
      show: {} as any,
      max_seats_per_booking: 8,
      bookable: true,
      seats: [],
    };

    // Sequence 4 is older than current 5
    state = seatSelectionReducer(state, {
      type: 'SET_MAP_DATA',
      payload: { data: staleMapData, etag: 'etag-old', sequence: 4 },
    });

    expect(state.pollSequence).toBe(5);
    expect(state.mapData).toBeNull();
  });
});
