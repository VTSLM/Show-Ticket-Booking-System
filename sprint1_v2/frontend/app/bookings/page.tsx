"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { bookingsApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function BookingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [bookings, setBookings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    if (user) {
      bookingsApi.list().then(setBookings).catch(() => {}).finally(() => setLoading(false));
    }
  }, [user, authLoading]);

  const fmt = (ts: string) => {
    try { return new Date(ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }); }
    catch { return ts; }
  };

  if (loading || authLoading) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">My Bookings</h1>
      {bookings.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-4">🎫</p>
          <p>No bookings yet.</p>
          <Link href="/browse" className="btn-primary mt-4 inline-block">Browse Shows</Link>
        </div>
      ) : (
        <div className="space-y-4">
          {bookings.map(b => (
            <Link key={b.id} href={`/bookings/${b.id}`}
              className="card flex gap-4 hover:shadow-lg transition-shadow">
              <div className="flex-1">
                <h3 className="font-semibold text-lg">{b.event_title}</h3>
                <p className="text-gray-500 text-sm">{b.venue_name}, {b.city}</p>
                <p className="text-gray-500 text-sm">{fmt(b.start_time)}</p>
                <p className="text-sm mt-1">{b.seat_count} seat(s) • <span className="font-bold text-red-500">₹{parseFloat(b.total_amount).toFixed(2)}</span></p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  b.status === "confirmed" ? "bg-green-100 text-green-700" :
                  b.status === "pending" ? "bg-yellow-100 text-yellow-700" :
                  "bg-red-100 text-red-700"
                }`}>{b.status}</span>
                {b.status === "pending" && (
                  <Link href={`/payment?booking_id=${b.id}`} onClick={e => e.stopPropagation()}
                    className="text-xs btn-primary py-1 px-3">Pay Now</Link>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
