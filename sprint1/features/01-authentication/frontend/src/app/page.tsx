// src/app/page.tsx
// Root redirect: send logged-in users to their role dashboard, others to /login.

"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function RootPage() {
  const { profile, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (profile && profile.status === "active") {
      router.replace(profile.redirect_to);
    } else if (profile && profile.status !== "active") {
      router.replace("/pending-approval");
    } else {
      router.replace("/login");
    }
  }, [loading, profile, router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
    </div>
  );
}
