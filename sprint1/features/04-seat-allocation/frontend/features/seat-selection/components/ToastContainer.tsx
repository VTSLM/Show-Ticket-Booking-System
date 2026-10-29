import React, { useEffect } from 'react';
import clsx from 'clsx';
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react';
import { useSeatSelection } from '../context/SeatSelectionContext';
import { ToastMessage } from '../context/seatSelectionReducer';

export const ToastContainer: React.FC = () => {
  const { state, dismissToast } = useSeatSelection();

  return (
    <div
      aria-live="assertive"
      className="fixed bottom-6 left-6 z-50 flex flex-col space-y-3 pointer-events-none max-w-sm w-full"
    >
      {state.toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}> = ({ toast, onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const icons = {
    info: <Info className="w-5 h-5 text-blue-400 flex-shrink-0" />,
    warning: <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0" />,
    error: <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />,
    success: <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />,
  };

  const borders = {
    info: 'border-blue-500/40 bg-[#10192A]',
    warning: 'border-amber-500/50 bg-[#251A0D]',
    error: 'border-red-500/50 bg-[#261014]',
    success: 'border-emerald-500/40 bg-[#0E201B]',
  };

  return (
    <div
      role="alert"
      className={clsx(
        'pointer-events-auto flex items-start justify-between p-3.5 rounded-xl border shadow-2xl backdrop-blur-md transition-all duration-200 animate-slide-up',
        borders[toast.type]
      )}
    >
      <div className="flex items-start space-x-3 mr-2">
        {icons[toast.type]}
        <p className="text-xs font-medium text-gray-200 leading-relaxed pt-0.5">
          {toast.message}
        </p>
      </div>

      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss message"
        className="text-gray-400 hover:text-white p-1 rounded-md transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
