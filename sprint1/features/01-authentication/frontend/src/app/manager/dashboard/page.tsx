"use client";
// src/app/manager/dashboard/page.tsx — Placeholder manager dashboard.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function ManagerDashboardPage() {
  const { profile, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!profile) { router.push("/login"); return; }
    if (!profile.roles.includes("manager") && !profile.roles.includes("admin")) {
      router.push("/");
    }
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
          <span className="text-2xl">🎬</span>
          <div>
            <h1 className="text-lg font-bold">Manager Dashboard</h1>
            <p className="text-xs text-gray-400">ShowBook Platform</p>
          </div>
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
        <span className="text-6xl">🎬</span>
        <h2 className="mt-4 text-2xl font-bold">Welcome, {profile.name}!</h2>
        <p className="mt-2 text-gray-400">
          You are logged in as a <span className="capitalize text-brand-400">{profile.roles[0]}</span>.
          Show listing and management features will appear here in the next sprint.
        </p>
        <div className="mt-8 inline-flex rounded-xl border border-gray-800 bg-gray-900 px-6 py-4">
          <p className="text-sm text-gray-500">
            Sprint 2 → Feature 02: Manager Show Listing
          </p>
        </div>
      </main>
    </div>
  );
}
