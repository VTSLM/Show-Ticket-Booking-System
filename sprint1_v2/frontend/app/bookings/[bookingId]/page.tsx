"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import toast from "react-hot-toast";
import Link from "next/link";

export default function BookingDetailPage() {
  const { bookingId } = useParams<{ bookingId: string }>();
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
      return;
    }

    if (user && bookingId) {
      bookingsApi
        .get(bookingId)
        .then(setBooking)
        .catch(() => toast.error("Booking not found"))
        .finally(() => setLoading(false));
    }
  }, [user, authLoading, bookingId, router]);

  const handleDownloadPdf = async () => {
    if (!user) {
      toast.error("Please log in again");
      return;
    }

    setDownloading(true);

    try {
      const token = await user.getIdToken();

      if (!token) {
        toast.error("Please log in again");
        return;
      }

      const API_URL =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      console.log("Downloading PDF...");
      console.log("Booking ID:", bookingId);
      console.log("Has auth token:", !!token);

      const response = await fetch(
        `${API_URL}/api/tickets/bookings/${bookingId}/pdf`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      console.log("PDF response status:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("PDF download failed:", errorText);

        if (response.status === 403) {
          toast.error("Authentication failed. Please log in again.");
        } else if (response.status === 404) {
          toast.error("Ticket not found.");
        } else {
          toast.error("Could not download ticket PDF");
        }

        return;
      }

      const blob = await response.blob();

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      a.download = `ticket_${bookingId.slice(0, 8)}.pdf`;

      document.body.appendChild(a);
      a.click();
      a.remove();

      window.URL.revokeObjectURL(url);

      toast.success("Ticket PDF downloaded");
    } catch (error) {
      console.error("PDF download error:", error);
      toast.error("Could not download ticket PDF");
    } finally {
      setDownloading(false);
    }
  };

  if (loading || authLoading) {
    return (
      <div className="text-center py-20 text-gray-400">
        Loading...
      </div>
    );
  }

  if (!booking) {
    return (
      <div className="text-center py-20 text-red-400">
        Booking not found.
      </div>
    );
  }

  const seats = booking.seats_info || [];

  return (
    <div className="max-w-lg mx-auto px-4 py-10">
      <div className="card">
        <div className="flex justify-between items-start mb-4">
          <h1 className="text-2xl font-bold">Booking Details</h1>

          <span
            className={`text-xs px-3 py-1 rounded-full font-semibold ${
              booking.status === "confirmed"
                ? "bg-green-100 text-green-700"
                : booking.status === "pending"
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {booking.status.toUpperCase()}
          </span>
        </div>

        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500">Booking ID</dt>
            <dd className="font-mono">
              {bookingId.slice(0, 16)}...
            </dd>
          </div>

          {seats.length > 0 && (
            <div className="flex justify-between">
              <dt className="text-gray-500">Seats</dt>
              <dd>
                {seats
                  .map(
                    (s: any) =>
                      `${s.row_label}${s.seat_number}`
                  )
                  .join(", ")}
              </dd>
            </div>
          )}

          <div className="border-t pt-3 flex justify-between font-bold text-lg">
            <dt>Total</dt>
            <dd className="text-red-500">
              ₹{parseFloat(booking.total_amount).toFixed(2)}
            </dd>
          </div>
        </dl>

        <div className="mt-6 space-y-3">
          {booking.status === "confirmed" ? (
            <>
              <button
                onClick={handleDownloadPdf}
                disabled={downloading}
                className="btn-primary w-full text-center block"
              >
                {downloading
                  ? "Downloading..."
                  : "Download Ticket PDF"}
              </button>

              <p className="text-center text-sm text-green-600">
                Ticket sent to your email!
              </p>
            </>
          ) : (
            <Link
              href={`/payment?booking_id=${bookingId}`}
              className="btn-primary w-full text-center block"
            >
              Complete Payment
            </Link>
          )}

          <Link
            href="/bookings"
            className="btn-secondary w-full text-center block"
          >
            All Bookings
          </Link>
        </div>
      </div>
    </div>
  );
}