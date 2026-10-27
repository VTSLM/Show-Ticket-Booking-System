/**
 * useToast.js
 * ===========
 * Lightweight toast notification system.
 * Returns { toasts, showToast } — showToast(title, message, type, duration).
 */

import { useState, useCallback } from 'react';

let idCounter = 0;

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((title, message = '', type = 'info', duration = 4000) => {
    const id = ++idCounter;
    setToasts(prev => [...prev, { id, title, message, type, exiting: false }]);

    setTimeout(() => {
      // Mark as exiting (triggers CSS exit animation)
      setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
      // Remove after animation
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 280);
    }, duration);
  }, []);

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 280);
  }, []);

  return { toasts, showToast, dismiss };
}
