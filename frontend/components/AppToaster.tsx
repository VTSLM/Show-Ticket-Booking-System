"use client";

import { Toaster, ToastBar, toast } from "react-hot-toast";

// Every notification gets a close button. The icon on an error toast looks
// like a close button but is only an icon, so users had no way to dismiss it.
export default function AppToaster() {
  return (
    <Toaster position="top-right" toastOptions={{ duration: 5000 }}>
      {(t) => (
        <ToastBar toast={t}>
          {({ icon, message }) => (
            <>
              {icon}
              {message}
              {t.type !== "loading" && (
                <button
                  type="button"
                  onClick={() => toast.dismiss(t.id)}
                  aria-label="Dismiss notification"
                  data-testid="toast-dismiss"
                  className="ml-1 shrink-0 rounded-md px-1.5 text-lg leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                >
                  ×
                </button>
              )}
            </>
          )}
        </ToastBar>
      )}
    </Toaster>
  );
}
