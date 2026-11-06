import { SeatMapData, SeatItem, MyHoldSummary } from '../types/seat';
import { computeClockOffset } from '../utils/clockOffset';

export interface ToastMessage {
  id: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'success';
}

export interface SeatSelectionState {
  showId: string;
  mapData: SeatMapData | null;
  selectedSeatIds: string[];
  etag: string | null;
  pollSequence: number;
  clockOffsetMs: number;
  myHold: MyHoldSummary | null;
  isSubmitting: boolean;
  errorBanner: string | null;
  reconnecting: boolean;
  holdExpiredModalOpen: boolean;
  toasts: ToastMessage[];
}

export type SeatSelectionAction =
  | {
      type: 'SET_MAP_DATA';
      payload: { data: SeatMapData; etag: string; sequence: number };
    }
  | { type: 'TOGGLE_SEAT'; payload: SeatItem }
  | { type: 'DESELECT_SEATS'; payload: string[] }
  | { type: 'CLEAR_SELECTION' }
  | { type: 'RESTORE_SELECTION'; payload: string[] }
  | { type: 'SET_HOLD'; payload: MyHoldSummary }
  | { type: 'CLEAR_HOLD' }
  | { type: 'SET_SUBMITTING'; payload: boolean }
  | { type: 'SET_RECONNECTING'; payload: boolean }
  | { type: 'SET_ERROR_BANNER'; payload: string | null }
  | { type: 'OPEN_HOLD_EXPIRED_MODAL' }
  | { type: 'CLOSE_HOLD_EXPIRED_MODAL' }
  | { type: 'ADD_TOAST'; payload: Omit<ToastMessage, 'id'> }
  | { type: 'REMOVE_TOAST'; payload: string };

export function createInitialState(showId: string): SeatSelectionState {
  return {
    showId,
    mapData: null,
    selectedSeatIds: [],
    etag: null,
    pollSequence: 0,
    clockOffsetMs: 0,
    myHold: null,
    isSubmitting: false,
    errorBanner: null,
    reconnecting: false,
    holdExpiredModalOpen: false,
    toasts: [],
  };
}

export function seatSelectionReducer(
  state: SeatSelectionState,
  action: SeatSelectionAction
): SeatSelectionState {
  switch (action.type) {
    case 'SET_MAP_DATA': {
      const { data, etag, sequence } = action.payload;

      // Discard stale out-of-order poll responses
      if (sequence < state.pollSequence) {
        return state;
      }

      const offsetMs = computeClockOffset(data.server_time);

      // Verify currently selected seats against incoming inventory
      const seatMap = new Map<string, SeatItem>();
      data.seats.forEach((s) => seatMap.set(s.show_seat_id, s));

      const validSelectedIds: string[] = [];
      const lostSeats: SeatItem[] = [];

      for (const id of state.selectedSeatIds) {
        const item = seatMap.get(id);
        if (item && (item.status === 'available' || item.is_mine)) {
          validSelectedIds.push(id);
        } else if (item) {
          lostSeats.push(item);
        }
      }

      let newToasts = [...state.toasts];
      if (lostSeats.length > 0) {
        const names = lostSeats.map((s) => `${s.row_label}${s.seat_number}`).join(', ');
        newToasts.push({
          id: `lost-${Date.now()}-${Math.random()}`,
          message: `Seat ${names} was taken by another user and removed from selection.`,
          type: 'warning',
        });
        if (newToasts.length > 3) newToasts = newToasts.slice(-3);
      }

      return {
        ...state,
        mapData: data,
        etag: etag || state.etag,
        pollSequence: sequence,
        clockOffsetMs: offsetMs,
        myHold: data.my_hold ?? state.myHold,
        selectedSeatIds: validSelectedIds,
        toasts: newToasts,
        reconnecting: false,
      };
    }

    case 'TOGGLE_SEAT': {
      const seat = action.payload;
      const isSelected = state.selectedSeatIds.includes(seat.show_seat_id);

      if (isSelected) {
        return {
          ...state,
          selectedSeatIds: state.selectedSeatIds.filter((id) => id !== seat.show_seat_id),
        };
      }

      // Check seat availability
      if (seat.status !== 'available' && !seat.is_mine) {
        return state;
      }

      const maxLimit = state.mapData?.max_seats_per_booking ?? 8;
      if (state.selectedSeatIds.length >= maxLimit) {
        const toastId = `max-${Date.now()}`;
        const newToasts = [...state.toasts, {
          id: toastId,
          message: `You can only select up to ${maxLimit} seats at once.`,
          type: 'warning' as const,
        }].slice(-3);

        return {
          ...state,
          toasts: newToasts,
        };
      }

      return {
        ...state,
        selectedSeatIds: [...state.selectedSeatIds, seat.show_seat_id],
      };
    }

    case 'DESELECT_SEATS': {
      const idsToRemove = new Set(action.payload);
      return {
        ...state,
        selectedSeatIds: state.selectedSeatIds.filter((id) => !idsToRemove.has(id)),
      };
    }

    case 'CLEAR_SELECTION':
      return {
        ...state,
        selectedSeatIds: [],
      };

    case 'RESTORE_SELECTION': {
      const validIds: string[] = [];
      if (state.mapData) {
        const availableSet = new Set(
          state.mapData.seats
            .filter((s) => s.status === 'available' || s.is_mine)
            .map((s) => s.show_seat_id)
        );
        action.payload.forEach((id) => {
          if (availableSet.has(id)) validIds.push(id);
        });
      } else {
        validIds.push(...action.payload);
      }

      return {
        ...state,
        selectedSeatIds: validIds.slice(0, state.mapData?.max_seats_per_booking ?? 8),
      };
    }

    case 'SET_HOLD':
      return {
        ...state,
        myHold: action.payload,
        selectedSeatIds: [],
        isSubmitting: false,
      };

    case 'CLEAR_HOLD':
      return {
        ...state,
        myHold: null,
      };

    case 'SET_SUBMITTING':
      return {
        ...state,
        isSubmitting: action.payload,
      };

    case 'SET_RECONNECTING':
      return {
        ...state,
        reconnecting: action.payload,
      };

    case 'SET_ERROR_BANNER':
      return {
        ...state,
        errorBanner: action.payload,
      };

    case 'OPEN_HOLD_EXPIRED_MODAL':
      return {
        ...state,
        holdExpiredModalOpen: true,
        myHold: null,
      };

    case 'CLOSE_HOLD_EXPIRED_MODAL':
      return {
        ...state,
        holdExpiredModalOpen: false,
      };

    case 'ADD_TOAST': {
      const newToast: ToastMessage = {
        ...action.payload,
        id: `toast-${Date.now()}-${Math.random()}`,
      };
      const toasts = [...state.toasts, newToast].slice(-3);
      return {
        ...state,
        toasts,
      };
    }

    case 'REMOVE_TOAST':
      return {
        ...state,
        toasts: state.toasts.filter((t) => t.id !== action.payload),
      };

    default:
      return state;
  }
}
