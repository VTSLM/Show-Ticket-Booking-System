"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { bookingsApi, paymentsApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

declare global { interface Window { Razorpay: any; } }

function PaymentForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, profile } = useAuth();
  const bookingId = params.get("booking_id") || "";
  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    if (!bookingId) return;
    bookingsApi.get(bookingId).then(setBooking).catch(() => toast.error("Booking not found")).finally(() => setLoading(false));
    // Load Razorpay script
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.body.appendChild(script);
    return () => { document.body.removeChild(script); };
  }, [bookingId]);

  const handlePay = async () => {
    if (!booking) return;
    setPaying(true);
    try {
      const order = await paymentsApi.createOrder(bookingId) as any;
      const options = {
        key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
        amount: order.amount,
        currency: order.currency,
        name: "TicketFlow",
        description: `Booking #${bookingId.slice(0, 8)}`,
        order_id: order.razorpay_order_id,
        prefill: { name: profile?.name, email: profile?.email },
        theme: { color: "#e94560" },
        handler: async (response: any) => {
          try {
            await paymentsApi.verify(bookingId, {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            // Generate ticket
            try {
              await ticketsApi.confirm(bookingId);
            } catch {}
            toast.success("Payment successful! Ticket emailed to you.");
            router.push(`/bookings/${bookingId}`);
          } catch (e: any) {
            toast.error(e.message || "Payment verification failed");
          }
        },
        modal: { ondismiss: () => setPaying(false) },
      };
      new window.Razorpay(options).open();
    } catch (e: any) {
      toast.error(e.message || "Could not initiate payment");
      setPaying(false);
    }
  };

  if (!user) return (
    <div className="text-center py-20">
      <p>Please <a href="/auth/login" className="text-red-500 underline">log in</a> to continue.</p>
    </div>
  );

  if (loading) return <div className="text-center py-20 text-gray-400">Loading booking...</div>;
  if (!booking) return <div className="text-center py-20 text-red-400">Booking not found.</div>;

  const seats = booking.seats_info || [];

  return (
    <div className="max-w-lg mx-auto px-4 py-10">
      <div className="card">
        <h1 className="text-2xl font-bold mb-4">Complete Payment</h1>
        <div className="space-y-3 text-sm mb-6">
          <div className="flex justify-between">
            <span className="text-gray-500">Booking ID</span>
            <span className="font-mono">{bookingId.slice(0, 16)}...</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Seats</span>
            <span>{seats.map((s: any) => `${s.row_label}${s.seat_number}`).join(", ") || `${seats.length} seats`}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Status</span>
            <span className={`px-2 py-0.5 rounded-full text-xs ${
              booking.status === "confirmed" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
            }`}>{booking.status}</span>
          </div>
          <div className="border-t pt-3 flex justify-between font-bold text-lg">
            <span>Total</span>
            <span className="text-red-500">₹{parseFloat(booking.total_amount).toFixed(2)}</span>
          </div>
        </div>

        {booking.status === "confirmed" ? (
          <div className="text-center">
            <p className="text-green-600 font-semibold mb-3">Payment already completed!</p>
            <a href={ticketsApi.pdfUrl(bookingId)} target="_blank"
              className="btn-primary inline-block">Download Ticket PDF</a>
          </div>
        ) : (
          <button onClick={handlePay} disabled={paying} className="btn-primary w-full text-lg py-3">
            {paying ? "Opening Razorpay..." : `Pay ₹${parseFloat(booking.total_amount).toFixed(2)}`}
          </button>
        )}
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return <Suspense><PaymentForm /></Suspense>;
}
