"use client";

import React from "react";

interface SessionTimeoutModalProps {
  isOpen: boolean;
  remainingSeconds: number;
  onStayLoggedIn: () => void;
  onLogoutNow: () => void;
  isExtending?: boolean;
}

export function SessionTimeoutModal({
  isOpen,
  remainingSeconds,
  onStayLoggedIn,
  onLogoutNow,
  isExtending = false,
}: SessionTimeoutModalProps) {
  if (!isOpen) return null;

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const formattedTime = `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-warning-title"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm px-4"
    >
      <div className="w-full max-w-md rounded-2xl border border-amber-500/30 bg-[#0d1522] p-6 shadow-2xl text-white">
        <div className="flex items-center space-x-3 text-amber-400 mb-4">
          <svg
            className="h-7 w-7 flex-shrink-0 animate-pulse text-amber-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <h2 id="session-warning-title" className="text-xl font-bold text-white">
            Session Expiring Soon
          </h2>
        </div>

        <p className="text-sm text-gray-300 leading-relaxed mb-4">
          You have been inactive. For your security, your session will automatically log out in:
        </p>

        <div className="flex items-center justify-center my-6">
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-6 py-3 font-mono text-3xl font-extrabold text-amber-300 tracking-wider">
            {formattedTime}
          </div>
        </div>

        <p className="text-xs text-gray-400 mb-6 text-center">
          Any pending payments or active seat holds will follow standard reservation rules and will not be altered.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={onStayLoggedIn}
            disabled={isExtending}
            className="flex-1 rounded-xl bg-amber-500 px-5 py-3 font-semibold text-black transition-all hover:bg-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 disabled:opacity-50"
          >
            {isExtending ? "Extending..." : "Stay Logged In"}
          </button>
          <button
            onClick={onLogoutNow}
            disabled={isExtending}
            className="rounded-xl border border-gray-700 bg-gray-800/60 px-5 py-3 font-medium text-gray-300 transition-all hover:bg-gray-700 hover:text-white"
          >
            Log Out Now
          </button>
        </div>
      </div>
    </div>
  );
}
