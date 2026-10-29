'use client';

import React, {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
} from 'react';
import { useRouter } from 'next/navigation';
import {
  seatSelectionReducer,
  createInitialState,
  SeatSelectionState,
  SeatSelectionAction,
} from './seatSelectionReducer';
import { SeatItem, RowBand } from '../types/seat';
import { buildSeatGrid } from '../utils/gridBuilder';
import { useSeatMapPolling } from '../hooks/useSeatMapPolling';
import {
  getCurrentUser,
  onAuthChange,
  signInDevUser,
  signOutUser,
  getIdToken,
} from '../services/firebaseAuth';
import {
  saveSeatSelection,
  getSavedSeatSelection,
  clearSavedSeatSelection,
} from '../services/sessionStorage';
import { apiClient, ApiError } from '../services/apiClient';

interface SeatSelectionContextValue {
  state: SeatSelectionState;
  dispatch: React.Dispatch<SeatSelectionAction>;
  user: { uid: string; email?: string } | null;
  bands: RowBand[];
  selectedSeats: SeatItem[];
  subtotal: number;
  convenienceFee: number;
  totalPrice: number;
  toggleSeat: (seat: SeatItem) => void;
  removeSeat: (seatId: string) => void;
  proceedToCheckout: () => Promise<void>;
  releaseCurrentHold: () => Promise<void>;
  loginAndContinue: () => Promise<void>;
  signOut: () => Promise<void>;
  handleHoldExpired: () => void;
  dismissToast: (id: string) => void;
  refetchMap: () => Promise<void>;
}

const SeatSelectionContext = createContext<SeatSelectionContextValue | undefined>(undefined);

export function SeatSelectionProvider({
  showId,
  children,
}: {
  showId: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [state, dispatch] = useReducer(seatSelectionReducer, showId, createInitialState);
  const [user, setUser] = useState<{ uid: string; email?: string } | null>(null);
  const isProceedingRef = useRef<boolean>(false);

  // 1. Listen for Firebase Auth changes
  useEffect(() => {
    setUser(getCurrentUser());
    const unsubscribe = onAuthChange((u) => {
      setUser(u);
    });
    return unsubscribe;
  }, []);

  // 2. Real-time live polling hook
  const { refetch } = useSeatMapPolling({
    showId,
    etag: state.etag,
    dispatch,
    enabled: !!showId,
    hasMapData: !!state.mapData,
  });


  // 3. Restore saved seat selection from sessionStorage once mapData loads
  const restoredOnceRef = useRef<boolean>(false);
  useEffect(() => {
    if (state.mapData && !restoredOnceRef.current) {
      restoredOnceRef.current = true;
      const savedIds = getSavedSeatSelection(showId);
      if (savedIds.length > 0) {
        dispatch({ type: 'RESTORE_SELECTION', payload: savedIds });
      }
    }
  }, [state.mapData, showId]);

  // 4. Persist selection changes into sessionStorage
  useEffect(() => {
    if (restoredOnceRef.current) {
      saveSeatSelection(showId, state.selectedSeatIds);
    }
  }, [showId, state.selectedSeatIds]);

  // 5. Best-effort hold release on page leave / unload
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (state.myHold?.booking_id) {
        // Asynchronously dispatch keepalive release
        getIdToken().then((token) => {
          apiClient.releaseHoldKeepalive(state.myHold!.booking_id, token);
        });
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [state.myHold]);

  // Derived Grid Bands
  const bands = useMemo(() => {
    return buildSeatGrid(state.mapData?.seats || []);
  }, [state.mapData?.seats]);

  // Derived Selected Seat Items
  const selectedSeats = useMemo(() => {
    if (!state.mapData?.seats) return [];
    const idSet = new Set(state.selectedSeatIds);
    return state.mapData.seats.filter((s) => idSet.has(s.show_seat_id));
  }, [state.mapData?.seats, state.selectedSeatIds]);

  // Pricing breakdown
  const subtotal = useMemo(() => {
    return selectedSeats.reduce((sum, s) => sum + s.price, 0);
  }, [selectedSeats]);

  // BookMyShow-style convenience fee (~12% or standard flat tier)
  const convenienceFee = useMemo(() => {
    if (subtotal === 0) return 0;
    return Math.round(subtotal * 0.12);
  }, [subtotal]);

  const totalPrice = subtotal + convenienceFee;

  // Actions
  const toggleSeat = useCallback((seat: SeatItem) => {
    if (state.myHold) {
      dispatch({
        type: 'ADD_TOAST',
        payload: {
          message: 'You already have active held seats. Please continue or release them first.',
          type: 'warning',
        },
      });
      return;
    }
    dispatch({ type: 'TOGGLE_SEAT', payload: seat });
  }, [state.myHold]);

  const removeSeat = useCallback((seatId: string) => {
    dispatch({ type: 'DESELECT_SEATS', payload: [seatId] });
  }, []);

  const dismissToast = useCallback((id: string) => {
    dispatch({ type: 'REMOVE_TOAST', payload: id });
  }, []);

  const handleHoldExpired = useCallback(() => {
    dispatch({ type: 'OPEN_HOLD_EXPIRED_MODAL' });
    refetch();
  }, [refetch]);

  const releaseCurrentHold = useCallback(async () => {
    if (!state.myHold) return;
    dispatch({ type: 'SET_SUBMITTING', payload: true });

    try {
      await apiClient.releaseHold(state.myHold.booking_id);
      dispatch({ type: 'CLEAR_HOLD' });
      dispatch({
        type: 'ADD_TOAST',
        payload: {
          message: 'Seats released successfully. You may select new seats.',
          type: 'info',
        },
      });
      await refetch();
    } catch (err: any) {
      dispatch({
        type: 'ADD_TOAST',
        payload: {
          message: err?.message || 'Failed to release hold.',
          type: 'error',
        },
      });
    } finally {
      dispatch({ type: 'SET_SUBMITTING', payload: false });
    }
  }, [state.myHold, refetch]);

  const loginAndContinue = useCallback(async () => {
    // Dev login simulation for local run
    await signInDevUser();
    setUser(getCurrentUser());
    dispatch({
      type: 'ADD_TOAST',
      payload: {
        message: 'Signed in successfully. Your seat selection was preserved.',
        type: 'success',
      },
    });
  }, []);

  const proceedToCheckout = useCallback(async () => {
    if (isProceedingRef.current || state.isSubmitting) return;

    if (state.selectedSeatIds.length === 0) {
      dispatch({
        type: 'ADD_TOAST',
        payload: {
          message: 'Please select at least 1 seat to proceed.',
          type: 'warning',
        },
      });
      return;
    }

    if (!user) {
      // Guest prompt
      await loginAndContinue();
      return;
    }

    isProceedingRef.current = true;
    dispatch({ type: 'SET_SUBMITTING', payload: true });

    const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `idem-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    try {
      const res = await apiClient.createHold(showId, state.selectedSeatIds, idempotencyKey);

      clearSavedSeatSelection(showId);
      dispatch({
        type: 'SET_HOLD',
        payload: {
          booking_id: res.booking_id,
          booking_number: res.booking_number,
          expires_at: res.expires_at,
          show_seat_ids: res.show_seat_ids,
          total_amount: res.total_amount,
        },
      });

      // Route to checkout template
      const template = process.env.NEXT_PUBLIC_CHECKOUT_PATH_TEMPLATE || '/checkout/{bookingId}';
      const checkoutUrl = template.replace('{bookingId}', res.booking_id);
      router.push(checkoutUrl);
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.code === 'SEATS_UNAVAILABLE') {
          // Deselect ONLY the failed seats, preserve the rest
          const failedIds: string[] = err.details?.failed_seat_ids || [];
          dispatch({ type: 'DESELECT_SEATS', payload: failedIds });

          // Format failed seat labels
          const failedSeatItems = (state.mapData?.seats || []).filter((s) =>
            failedIds.includes(s.show_seat_id)
          );
          const failedNames = failedSeatItems.length > 0
            ? failedSeatItems.map((s) => `${s.row_label}${s.seat_number}`).join(' and ')
            : 'Some of your seats';

          dispatch({
            type: 'ADD_TOAST',
            payload: {
              message: `${failedNames} were just taken. Your other seats remain selected.`,
              type: 'error',
            },
          });
          refetch();
        } else if (err.code === 'SHOW_NOT_BOOKABLE') {
          dispatch({
            type: 'ADD_TOAST',
            payload: {
              message: err.message,
              type: 'error',
            },
          });
          refetch();
        } else if (err.code === 'UNAUTHENTICATED') {
          dispatch({
            type: 'ADD_TOAST',
            payload: {
              message: 'Your session has expired. Please sign in again.',
              type: 'warning',
            },
          });
          await signOutUser();
          setUser(null);
        } else {
          dispatch({
            type: 'ADD_TOAST',
            payload: {
              message: err.message || 'We experienced an issue holding your seats. Please try again.',
              type: 'error',
            },
          });
        }
      } else {
        dispatch({
          type: 'ADD_TOAST',
          payload: {
            message: 'Unable to connect to the booking servers. Please check your internet connection.',
            type: 'error',
          },
        });
      }
    } finally {
      isProceedingRef.current = false;
      dispatch({ type: 'SET_SUBMITTING', payload: false });
    }
  }, [
    state.isSubmitting,
    state.selectedSeatIds,
    state.mapData?.seats,
    showId,
    user,
    loginAndContinue,
    router,
    refetch,
  ]);

  const value = useMemo<SeatSelectionContextValue>(
    () => ({
      state,
      dispatch,
      user,
      bands,
      selectedSeats,
      subtotal,
      convenienceFee,
      totalPrice,
      toggleSeat,
      removeSeat,
      proceedToCheckout,
      releaseCurrentHold,
      loginAndContinue,
      signOut: async () => {
        await signOutUser();
        setUser(null);
      },
      handleHoldExpired,
      dismissToast,
      refetchMap: refetch,
    }),
    [
      state,
      user,
      bands,
      selectedSeats,
      subtotal,
      convenienceFee,
      totalPrice,
      toggleSeat,
      removeSeat,
      proceedToCheckout,
      releaseCurrentHold,
      loginAndContinue,
      handleHoldExpired,
      dismissToast,
      refetch,
    ]
  );

  return (
    <SeatSelectionContext.Provider value={value}>
      {children}
    </SeatSelectionContext.Provider>
  );
}

export function useSeatSelection() {
  const context = useContext(SeatSelectionContext);
  if (!context) {
    throw new Error('useSeatSelection must be used within a SeatSelectionProvider');
  }
  return context;
}
