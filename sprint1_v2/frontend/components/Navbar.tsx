"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function Navbar() {
  const { profile, loading, logout, isManager, isAdmin } = useAuth();
  const router = useRouter();

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
            <Link href="/support" className="hover:text-red-300">
              Support
            </Link>

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
              <Link href="/manager" className="hover:text-red-300">
                Manager
              </Link>
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
              </>
            )}

            <span className="hidden text-gray-400 sm:inline" aria-hidden="true">
              |
            </span>

            <span className="text-gray-300">{profile.name}</span>

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