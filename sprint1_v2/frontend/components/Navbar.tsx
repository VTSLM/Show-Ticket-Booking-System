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
    <nav className="bg-[#1a1a2e] text-white px-6 py-3 flex items-center justify-between shadow-lg">
      <Link href="/" className="text-xl font-bold text-[#287cff]">
        🎫 TicketFlow
      </Link>
      <div className="flex items-center gap-4 text-sm">
        <Link href="/browse" className="hover:text-red-300 transition-colors">Browse Shows</Link>
        <Link href="/help" className="hover:text-red-300 transition-colors">Help</Link>
        {!loading && profile ? (
          <>
            <Link href="/bookings" className="hover:text-red-300">My Bookings</Link>
            <Link href="/support" className="hover:text-red-300">Support</Link>
            {isManager && (
              <Link href="/manager" className="hover:text-red-300">Manager</Link>
            )}
            {isAdmin && (
              <Link href="/admin" className="hover:text-red-300">Admin</Link>
            )}
            <span className="text-gray-400">|</span>
            <span className="text-gray-300">{profile.name}</span>
            <button onClick={handleLogout} className="btn-primary text-xs py-1 px-3">Logout</button>
          </>
        ) : !loading ? (
          <>
            <Link href="/auth/login" className="hover:text-red-300">Login</Link>
            <Link href="/auth/register" className="btn-primary text-xs py-1 px-3">Register</Link>
          </>
        ) : null}
      </div>
    </nav>
  );
}
