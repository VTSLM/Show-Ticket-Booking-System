"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import NotificationBell from "@/components/NotificationBell";
import { useLocation } from "@/contexts/LocationContext";

export default function Navbar() {
  const { profile, loading, logout, isManager, isAdmin } = useAuth();
  const router = useRouter();
  const { location, openPicker } = useLocation();

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 bg-[#1a1a2e] px-4 py-3 text-white shadow-lg sm:px-6">
      <Link href="/" className="whitespace-nowrap text-xl font-bold text-[#287cff]">
        🎫 TicketFlow
      </Link>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <button
          type="button"
          onClick={openPicker}
          title="Set your location to see shows within 100 km"
          className="flex max-w-[11rem] items-center gap-1.5 rounded-full border border-slate-600 px-3 py-1 text-xs font-medium transition-colors hover:border-[#287cff] hover:text-white"
        >
          <span aria-hidden="true">📍</span>
          <span className="truncate">{location ? location.label : "Set location"}</span>
          <span aria-hidden="true" className="text-[10px] text-slate-400">▾</span>
        </button>
        <Link href="/browse" className="transition-colors hover:text-red-300">
          Browse Shows
        </Link>
        <Link href="/help" className="transition-colors hover:text-red-300">
          Help
        </Link>

        {!loading && profile ? (
          <>
            <Link href="/bookings" className="hover:text-red-300">
              My Bookings
            </Link>
            <Link href="/wishlist" className="hover:text-red-300">
              ❤️ Wishlist
            </Link>
            <Link href="/support" className="hover:text-red-300">
              Support
            </Link>

            <NotificationBell />

            {isManager && !isAdmin && (
              <>
                <Link href="/verification/organizer" className="hover:text-red-300">
                  Organizer Verification
                </Link>
                <Link href="/venue-verification" className="hover:text-red-300">
                  Venue Verification
                </Link>
              </>
            )}
            {isManager && (
              <>
                <Link href="/manager" className="hover:text-red-300">
                  Manager
                </Link>
                <Link href="/manager/analytics" className="hover:text-red-300">
                  Analytics
                </Link>
              </>
            )}

            {isAdmin && (
              <>
                <Link href="/admin" className="hover:text-red-300">
                  Admin
                </Link>
                <Link href="/admin/venue-reviews" className="hover:text-red-300">
                  Venue Reviews
                </Link>
                <Link href="/admin/organizer-reviews" className="hover:text-red-300">
                  Organizer Reviews
                </Link>
                <Link href="/admin/organizers" className="hover:text-red-300">
                  Organizers
                </Link>
                <Link href="/admin/users" className="hover:text-red-300">
                  Users
                </Link>
                <Link href="/admin/cancellations" className="hover:text-red-300">
                  Cancellations & Refunds
                </Link>
              </>
            )}

            <span className="hidden text-gray-400 sm:inline" aria-hidden="true">
              |
            </span>

            <Link
              href="/profile"
              className="text-gray-300 underline-offset-4 hover:text-white hover:underline"
              title="View and edit your profile"
            >
              {profile.name}
            </Link>

            <button
              type="button"
              onClick={handleLogout}
              className="btn-primary px-3 py-1 text-xs"
            >
              Logout
            </button>
          </>
        ) : !loading ? (
          <>
            <Link href="/auth/login" className="hover:text-red-300">
              Login
            </Link>
            <Link href="/auth/register" className="btn-primary px-3 py-1 text-xs">
              Register
            </Link>
          </>
        ) : null}
      </div>
    </nav>
  );
}