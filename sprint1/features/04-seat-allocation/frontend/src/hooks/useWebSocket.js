/**
 * useWebSocket.js
 * ===============
 * Custom hook for real-time seat status updates (Phase 6).
 * 
 * Connects to /ws/{showId} and listens for SEAT_UPDATE messages.
 * Applies received updates directly to the seat store — no full refetch.
 * 
 * The hook manages reconnection automatically on disconnect.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { getWsUrl } from '../api';

const RECONNECT_DELAY_MS = 3000;

export function useWebSocket(showId, onSeatUpdate) {
  const [wsStatus, setWsStatus] = useState('disconnected'); // 'connecting' | 'connected' | 'disconnected'
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    setWsStatus('connecting');

    const ws = new WebSocket(getWsUrl(showId));
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mounted.current) return;
      setWsStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'SEAT_UPDATE') {
          onSeatUpdate(msg.seat_id, msg.status);
        }
      } catch (e) {
        console.warn('WS parse error:', e);
      }
    };

    ws.onclose = () => {
      if (!mounted.current) return;
      setWsStatus('disconnected');
      // Auto-reconnect after delay
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [showId, onSeatUpdate]);

  useEffect(() => {
    mounted.current = true;
    connect();

    return () => {
      mounted.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  return wsStatus;
}
