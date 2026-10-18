"use client";
// src/app/browse/page.tsx — Customer home / browse shows placeholder.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function BrowsePage() {
  const { profile, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!profile) { router.push("/login"); return; }
    if (profile.status !== "active") { router.push("/pending-approval"); return; }
  }, [loading, profile, router]);

  if (loading || !profile) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🎭</span>
          <h1 className="text-lg font-bold">ShowBook</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">
            {profile.name} &middot; <span className="text-brand-400 capitalize">{profile.roles[0]}</span>
          </span>
          <button
            onClick={logout}
            className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800 transition"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-16 text-center">
        <span className="text-6xl">🎟️</span>
        <h2 className="mt-4 text-2xl font-bold">Hi {profile.name}, welcome to ShowBook!</h2>
        <p className="mt-2 text-gray-400">
          Browse nearby shows and book tickets. This section will be fully built in Sprint 2.
        </p>
        <div className="mt-8 inline-flex rounded-xl border border-gray-800 bg-gray-900 px-6 py-4">
          <p className="text-sm text-gray-500">
            Sprint 2 → Feature 03: Browse Nearby Shows
          </p>
        </div>
      </main>
    </div>
  );
}
