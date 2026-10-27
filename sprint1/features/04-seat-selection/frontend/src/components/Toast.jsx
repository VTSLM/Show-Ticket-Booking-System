/**
 * Toast.jsx — Toast notification renderer
 */

import { useToast } from '../hooks/useToast';

const ICONS = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
};

export function ToastContainer({ toasts, dismiss }) {
  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type} ${toast.exiting ? 'toast-exit' : ''}`}
          onClick={() => dismiss(toast.id)}
          style={{ cursor: 'pointer' }}
        >
          <span className="toast-icon">{ICONS[toast.type]}</span>
          <div className="toast-content">
            <div className="toast-title">{toast.title}</div>
            {toast.message && <div className="toast-message">{toast.message}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
