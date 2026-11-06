"use client";
// src/app/pending-approval/page.tsx
// Shown to managers/admins who have registered but are awaiting admin approval.

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export default function PendingApprovalPage() {
  const { profile, logout } = useAuth();

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-amber-700/10 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-amber-500/5 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md text-center">
        <div className="mb-6 flex justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-amber-500/30 bg-amber-900/20">
            <span className="text-4xl">⏳</span>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-white">Awaiting Approval</h1>
        <p className="mt-3 text-gray-400">
          Hi <strong className="text-white">{profile?.name ?? "there"}</strong>! Your{" "}
          <span className="capitalize text-amber-400">
            {profile?.roles?.[0] ?? "account"}
          </span>{" "}
          registration has been submitted successfully.
        </p>
        <p className="mt-2 text-sm text-gray-500">
          An administrator will review your request and activate your account. You will be
          able to log in once approved.
        </p>

        <div className="mt-8 rounded-xl border border-gray-800 bg-gray-900 p-5 text-left space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-green-400">✓</span>
            <span className="text-sm text-gray-300">Firebase account created</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-green-400">✓</span>
            <span className="text-sm text-gray-300">Profile submitted to platform</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-amber-400">⧗</span>
            <span className="text-sm text-gray-300">Admin review &amp; approval</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-gray-600">○</span>
            <span className="text-sm text-gray-500">Account activated — ready to log in</span>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3">
          <button
            onClick={logout}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm font-medium text-gray-300 transition hover:bg-gray-700"
          >
            Sign out
          </button>
          <Link
            href="/login"
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-center text-sm font-semibold text-white transition hover:bg-brand-500"
          >
            Try logging in again
          </Link>
        </div>
      </div>
    </main>
  );
}
