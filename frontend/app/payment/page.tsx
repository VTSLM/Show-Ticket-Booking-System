"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Script from "next/script";
import toast from "react-hot-toast";
import { friendlyErrorMessage } from "@/lib/errorMessages";
import { bookingsApi, paymentsApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface PaymentVerification {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  prefill: { name?: string; email?: string; contact: string };
  theme: { color: string };
  retry: { enabled: boolean };
  handler: (response: PaymentVerification) => Promise<void>;
  modal: { ondismiss: () => void };
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => {
      open: () => void;
      on: (event: "payment.failed", handler: () => void) => void;
    };
  }
}

function PaymentForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, profile, loading: authLoading } = useAuth();
  const bookingId = params.get("booking_id") || "";
  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [checkoutReady, setCheckoutReady] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [verification, setVerification] = useState<PaymentVerification | null>(null);
  const [phone, setPhone] = useState<string | null>(null);
  const contact = phone ?? profile?.phone ?? "";

  useEffect(() => {
    if (!bookingId || authLoading || !user) return;
    let active = true;
    setLoading(true);
    setVerification(null);
    setCheckoutError("");
    bookingsApi.get(bookingId)
      .then((result) => { if (active) setBooking(result); })
      .catch(() => { if (active) setBooking(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [bookingId, authLoading, user]);

  const verifyCheckout = async (response: PaymentVerification) => {
    setVerification(response);
    setVerifying(true);
    setCheckoutError("");
    try {
      await paymentsApi.verify(bookingId, response);
    } catch {
      setCheckoutError("We could not confirm your payment. Retry verification before trying to pay again.");
      setVerifying(false);
      return;
    }
    try {
      await ticketsApi.confirm(bookingId);
      toast.success("Payment confirmed. Your ticket is available in My Bookings.");
    } catch {
      toast.error("Payment confirmed. Open My Bookings to try downloading your ticket.");
    }
    router.push(`/bookings/${bookingId}`);
  };

  const handlePay = async () => {
    const Razorpay = window.Razorpay;
    if (!Razorpay || !booking || booking.status !== "pending" || paying || verification) return;

    const digits = contact.trim().replace(/[\s()-]/g, "");
    const paymentContact = /^\d{10}$/.test(digits) ? `+91${digits}` : digits;
    if (!/^\+[1-9]\d{7,14}$/.test(paymentContact)) {
      setCheckoutError("Enter a valid mobile number with its country code for Razorpay.");
      return;
    }

    setCheckoutError("");
    setPaying(true);
    try {
      const order = await paymentsApi.createOrder(bookingId);
      const checkout = new Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: "TicketFlow",
        description: `Booking ${bookingId.slice(0, 8)}`,
        order_id: order.razorpay_order_id,
        prefill: { name: profile?.name, email: profile?.email, contact: paymentContact },
        theme: { color: "#e94560" },
        retry: { enabled: false },
        handler: verifyCheckout,
        modal: { ondismiss: () => setPaying(false) },
      });
      checkout.on("payment.failed", () => {
        setCheckoutError("Razorpay could not complete the payment. You can retry with the same booking.");
      });
      checkout.open();
    } catch (error) {
      setCheckoutError(friendlyErrorMessage(error, "Could not open checkout. Please try again."));
      setPaying(false);
    }
  };

  const handleDownloadPdf = async () => {
    try {
      const token = await user?.getIdToken();

      if (!token) {
        toast.error("Please log in again");
        return;
      }

      const API_URL =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      const response = await fetch(
        `${API_URL}/api/tickets/bookings/${bookingId}/pdf`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const error = await response.text();
        console.error("PDF download failed:", error);
        toast.error("Could not download ticket PDF");
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
  const total = Number(booking.total_amount);
  const canPay = booking.status === "pending" && total > 0;

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
            <button
              onClick={handleDownloadPdf}
              className="btn-primary inline-block"
            >
              Download Ticket PDF
            </button>
          </div>
        ) : verification ? (
          <button onClick={() => verifyCheckout(verification)} disabled={verifying} className="btn-primary w-full py-3">
            {verifying ? "Verifying payment…" : "Retry payment verification"}
          </button>
        ) : canPay ? (
          <>
            <Script
              src="https://checkout.razorpay.com/v1/checkout.js"
              onReady={() => setCheckoutReady(true)}
              onError={() => setCheckoutError("Razorpay could not load. Refresh this page to try again.")}
            />
            <label htmlFor="payment-contact" className="block text-sm mb-1">Mobile number for Razorpay</label>
            <input
              id="payment-contact"
              type="tel"
              autoComplete="tel"
              placeholder="+91 90000 90000"
              className="input w-full mb-3"
              value={contact}
              onChange={(event) => setPhone(event.target.value)}
              disabled={paying}
            />
            <button onClick={handlePay} disabled={!checkoutReady || paying} className="btn-primary w-full text-lg py-3">
              {paying ? "Opening Razorpay…" : `Pay ₹${total.toFixed(2)}`}
            </button>
          </>
        ) : (
          <p>{booking.status === "pending"
            ? "Online payment requires a booking total greater than ₹0."
            : "This booking is no longer available for payment."}</p>
        )}
        {checkoutError && <p role="alert" className="mt-3 text-sm text-red-400">{checkoutError}</p>}
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return <Suspense><PaymentForm /></Suspense>;
}
