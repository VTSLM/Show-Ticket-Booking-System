import { useEffect, useRef, useCallback } from 'react';
import { apiClient, ApiError } from '../services/apiClient';
import { SeatSelectionAction } from '../context/seatSelectionReducer';

interface UseSeatMapPollingOptions {
  showId: string;
  etag: string | null;
  dispatch: React.Dispatch<SeatSelectionAction>;
  enabled: boolean;
  /** Whether mapData has been loaded at least once (passed from context). */
  hasMapData: boolean;
}

const BASE_POLL_INTERVAL_MS = 4000;
const MAX_BACKOFF_MS = 30000;
/** Hard timeout: if first load hasn't succeeded by this point, show the error UI. */
const INITIAL_LOAD_TIMEOUT_MS = 8000;

export function useSeatMapPolling({
  showId,
  etag,
  dispatch,
  enabled,
  hasMapData,
}: UseSeatMapPollingOptions) {
  const sequenceRef = useRef<number>(0);
  const etagRef = useRef<string | null>(etag);
  const backoffRef = useRef<number>(BASE_POLL_INTERVAL_MS);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isFetchingRef = useRef<boolean>(false);
  const hasMapDataRef = useRef<boolean>(hasMapData);
  const initialTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    etagRef.current = etag;
  }, [etag]);

  useEffect(() => {
    hasMapDataRef.current = hasMapData;
  }, [hasMapData]);

  const fetchLatestMap = useCallback(async () => {
    if (isFetchingRef.current || !enabled || !showId) return;

    isFetchingRef.current = true;
    const currentSeq = ++sequenceRef.current;

    try {
      const result = await apiClient.getSeatMap(showId, etagRef.current);

      if (!result.notModified) {
        dispatch({
          type: 'SET_MAP_DATA',
          payload: {
            data: result.data,
            etag: result.etag,
            sequence: currentSeq,
          },
        });
        etagRef.current = result.etag;
      }

      // Success — reset backoff and clear any error banner
      backoffRef.current = BASE_POLL_INTERVAL_MS;
      dispatch({ type: 'SET_RECONNECTING', payload: false });
      dispatch({ type: 'SET_ERROR_BANNER', payload: null });

      // Cancel the initial-load hard timeout — data arrived
      if (initialTimeoutRef.current) {
        clearTimeout(initialTimeoutRef.current);
        initialTimeoutRef.current = null;
      }
    } catch (err: any) {
      const isNetwork = err instanceof ApiError && err.code === 'NETWORK_ERROR';

      if (!hasMapDataRef.current) {
        // First load failed — surface a clear error message immediately
        let msg =
          'Unable to load seat map. The show may not exist or the server is unavailable.';
        if (isNetwork) {
          msg =
            'Unable to connect to the booking server. Please check your internet connection and try again.';
        } else if (err instanceof ApiError) {
          if (err.code === 'SHOW_NOT_FOUND') {
            msg =
              'This show could not be found. It may have been cancelled or the link is incorrect.';
          } else if (err.message) {
            msg = err.message;
          }
        }
        dispatch({ type: 'SET_ERROR_BANNER', payload: msg });
      } else {
        // Subsequent poll failure — only show the reconnecting indicator; never reset the map
        if (isNetwork) {
          dispatch({ type: 'SET_RECONNECTING', payload: true });
        }
      }

      // Exponential backoff regardless
      backoffRef.current = Math.min(backoffRef.current * 1.5, MAX_BACKOFF_MS);
    } finally {
      isFetchingRef.current = false;
    }
  }, [showId, enabled, dispatch]);

  // Schedule recurring poll loop
  const scheduleNextPoll = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        await fetchLatestMap();
      }
      scheduleNextPoll();
    }, backoffRef.current);
  }, [fetchLatestMap]);

  useEffect(() => {
    if (!enabled || !showId) return;

    // Hard timeout: if nothing loads in INITIAL_LOAD_TIMEOUT_MS, show error UI
    initialTimeoutRef.current = setTimeout(() => {
      if (!hasMapDataRef.current) {
        dispatch({
          type: 'SET_ERROR_BANNER',
          payload:
            'Seat map is taking too long to load. The server may be starting up — please retry.',
        });
      }
    }, INITIAL_LOAD_TIMEOUT_MS);

    // Initial fetch
    fetchLatestMap();
    scheduleNextPoll();

    // Pause when tab hidden, re-fetch immediately on focus
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchLatestMap();
        scheduleNextPoll();
      } else {
        if (timerRef.current) clearTimeout(timerRef.current);
      }
    };

    const handleWindowFocus = () => {
      fetchLatestMap();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (initialTimeoutRef.current) clearTimeout(initialTimeoutRef.current);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [showId, enabled, fetchLatestMap, scheduleNextPoll]);

  return { refetch: fetchLatestMap };
}
