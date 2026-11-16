"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { bookingsApi } from "@/lib/api";
import { searchFaqs } from "@/lib/faqs";
import {
  supportApi,
  SupportCategory,
  CATEGORY_LABELS,
  BOOKING_REQUIRED,
  formatDateTime,
} from "@/lib/supportApi";

const SUBJECT_MIN = 5, SUBJECT_MAX = 150;
const MESSAGE_MIN = 10, MESSAGE_MAX = 2000;

function NewSupportRequestForm() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  const [bookings, setBookings] = useState<any[]>([]);
  const [category, setCategory] = useState<SupportCategory>(
    (params.get("category") as SupportCategory) in CATEGORY_LABELS
      ? (params.get("category") as SupportCategory)
      : "booking"
  );
  const [bookingId, setBookingId] = useState(params.get("booking_id") || "");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [openFaq, setOpenFaq] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login"); return; }
    if (user) bookingsApi.list().then(setBookings).catch(() => {});
  }, [user, authLoading, router]);

  // "Smart FAQ": suggest answers while the customer describes the problem.
  const suggestions = useMemo(() => searchFaqs(subject, 3), [subject]);

  const bookingRequired = BOOKING_REQUIRED.includes(category);

  const validate = () => {
    const e: Record<string, string> = {};
    const s = subject.trim(), m = message.trim();
    if (s.length < SUBJECT_MIN) e.subject = `Subject must be at least ${SUBJECT_MIN} characters.`;
    if (s.length > SUBJECT_MAX) e.subject = `Subject must be under ${SUBJECT_MAX} characters.`;
    if (m.length < MESSAGE_MIN) e.message = `Please describe the problem in at least ${MESSAGE_MIN} characters.`;
    if (m.length > MESSAGE_MAX) e.message = `Message must be under ${MESSAGE_MAX} characters.`;
    if (bookingRequired && !bookingId) e.booking = "Please select the booking this is about.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      const created = await supportApi.create({
        category,
        subject: subject.trim(),
        message: message.trim(),
        booking_id: bookingId || undefined,
      });
      toast.success(`Request ${created.request_number} sent! We'll get back to you soon.`);
      router.push(`/support/${created.id}`);
    } catch (err: any) {
      toast.error(err.message || "Could not send your request");
      setSubmitting(false);
    }
  };

  if (authLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <Link href="/support" className="text-sm text-slate-400 hover:text-blue-400">← My Requests</Link>
      <h1 className="text-3xl font-bold tracking-tight text-white mt-2 mb-6">Contact Support</h1>

      <form onSubmit={handleSubmit} className="card p-6 space-y-5" noValidate>
        <div>
          <label htmlFor="category" className="block text-sm font-medium text-slate-200 mb-1">What do you need help with?</label>
          <select
            id="category"
            className="input"
            value={category}
            onChange={e => setCategory(e.target.value as SupportCategory)}
          >
            {(Object.keys(CATEGORY_LABELS) as SupportCategory[]).map(c => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="booking" className="block text-sm font-medium text-slate-200 mb-1">
            Booking {bookingRequired ? <span className="text-red-400">*</span> : <span className="text-slate-500">(optional)</span>}
          </label>
          <select
            id="booking"
            className="input"
            value={bookingId}
            onChange={e => setBookingId(e.target.value)}
          >
            <option value="">— {bookingRequired ? "Select a booking" : "Not about a specific booking"} —</option>
            {bookings.map(b => (
              <option key={b.id} value={b.id}>
                {b.event_title} • {formatDateTime(b.start_time)} • ₹{parseFloat(b.total_amount).toFixed(0)} ({b.status})
              </option>
            ))}
          </select>
          {bookings.length === 0 && bookingRequired && (
            <p className="text-xs text-slate-400 mt-1">You don&apos;t have any bookings yet.</p>
          )}
          {errors.booking && <p className="text-xs text-red-400 mt-1">{errors.booking}</p>}
        </div>

        <div>
          <label htmlFor="subject" className="block text-sm font-medium text-slate-200 mb-1">Subject</label>
          <input
            id="subject"
            className="input"
            placeholder="e.g. Payment done but booking still pending"
            value={subject}
            maxLength={SUBJECT_MAX}
            onChange={e => setSubject(e.target.value)}
          />
          {errors.subject && <p className="text-xs text-red-400 mt-1">{errors.subject}</p>}
        </div>

        {suggestions.length > 0 && (
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-300 mb-2">💡 These answers might help:</p>
            <ul className="space-y-2">
              {suggestions.map(f => (
                <li key={f.id} className="text-sm">
                  <button
                    type="button"
                    onClick={() => setOpenFaq(openFaq === f.id ? null : f.id)}
                    className="text-blue-400 hover:underline text-left"
                  >
                    {f.question}
                  </button>
                  {openFaq === f.id && <p className="text-slate-300 mt-1">{f.answer}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <label htmlFor="message" className="block text-sm font-medium text-slate-200 mb-1">Describe the problem</label>
          <textarea
            id="message"
            className="input min-h-[140px]"
            placeholder="Tell us what happened, when, and any payment/transaction ID if you have it."
            value={message}
            maxLength={MESSAGE_MAX}
            onChange={e => setMessage(e.target.value)}
          />
          <div className="flex justify-between text-xs mt-1">
            <span className="text-red-400">{errors.message}</span>
            <span className="text-slate-500">{message.length}/{MESSAGE_MAX}</span>
          </div>
        </div>

        <button type="submit" disabled={submitting} className="btn-primary w-full disabled:opacity-60">
          {submitting ? "Sending..." : "Send Request"}
        </button>
      </form>
    </div>
  );
}

export default function NewSupportRequestPage() {
  // useSearchParams() needs a Suspense boundary in Next.js 14.
  return (
    <Suspense fallback={<div className="text-center py-20 text-slate-500">Loading...</div>}>
      <NewSupportRequestForm />
    </Suspense>
  );
}
