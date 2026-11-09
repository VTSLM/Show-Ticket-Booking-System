// Customer Care — Frequently Asked Questions shown on /help
// and suggested while a customer types a new support request.
import type { SupportCategory } from "./supportApi";

export interface Faq {
  id: string;
  category: SupportCategory;
  question: string;
  answer: string;
  keywords: string[];
}

export const FAQS: Faq[] = [
  {
    id: "payment-deducted-no-ticket",
    category: "payment",
    question: "Money was deducted but my booking still shows “pending”. What should I do?",
    answer:
      "Sometimes the bank confirms the payment a few minutes late. Wait 10–15 minutes and refresh “My Bookings”. If it is still pending, raise a Payment issue request and pick that booking — we will check it with Razorpay. If the payment failed, the amount is returned to your account automatically in 5–7 working days.",
    keywords: ["deducted", "debited", "pending", "money", "cut", "charged", "failed", "razorpay"],
  },
  {
    id: "payment-methods",
    category: "payment",
    question: "Which payment methods can I use?",
    answer:
      "Payments go through Razorpay, so you can pay with UPI, debit/credit cards, net banking and popular wallets.",
    keywords: ["upi", "card", "wallet", "netbanking", "method", "pay"],
  },
  {
    id: "payment-twice",
    category: "payment",
    question: "I was charged twice for the same booking.",
    answer:
      "Raise a Payment issue request and select the booking. Our team will verify both transactions and refund the extra one.",
    keywords: ["twice", "double", "two times", "duplicate", "charged"],
  },
  {
    id: "ticket-not-received",
    category: "booking",
    question: "I didn’t get my ticket email.",
    answer:
      "Check your spam/promotions folder first. You can always download the ticket PDF from My Bookings → open the booking → “Download Ticket PDF”.",
    keywords: ["email", "mail", "ticket", "pdf", "received", "download"],
  },
  {
    id: "change-seats",
    category: "booking",
    question: "Can I change my seats after booking?",
    answer:
      "Seats can’t be changed after a booking is confirmed. If there is a problem with your seats, raise a Booking issue request and we’ll help.",
    keywords: ["seat", "change", "swap", "move"],
  },
  {
    id: "show-cancelled",
    category: "refund",
    question: "The show was cancelled. Will I get my money back?",
    answer:
      "Yes. If the organiser cancels a show you get a full refund to your original payment method. Raise a Refund request if you haven’t received it within 7 working days.",
    keywords: ["cancelled", "canceled", "show", "refund", "postponed"],
  },
  {
    id: "refund-time",
    category: "refund",
    question: "How long does a refund take?",
    answer:
      "Once approved, refunds usually reach your account in 5–7 working days, depending on your bank.",
    keywords: ["refund", "how long", "days", "time", "money back"],
  },
  {
    id: "cancel-booking",
    category: "refund",
    question: "Can I cancel my booking and get a refund?",
    answer:
      "Raise a Refund request and select the booking. Our team will review it based on the organiser’s cancellation policy.",
    keywords: ["cancel", "refund", "booking"],
  },
  {
    id: "forgot-password",
    category: "account",
    question: "I forgot my password.",
    answer: "On the Login page, use “Forgot password?” to get a reset link on your email.",
    keywords: ["password", "forgot", "reset", "login"],
  },
  {
    id: "account-pending",
    category: "account",
    question: "My manager account is still waiting for approval.",
    answer:
      "Manager accounts are approved by an admin. This usually takes 1–2 working days. If it takes longer, raise an Account / login request.",
    keywords: ["manager", "approval", "pending", "approve", "account"],
  },
];

/** Returns FAQs whose question or keywords match the given text (used for search + suggestions). */
export function searchFaqs(text: string, limit?: number): Faq[] {
  const words = text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(w => w.length >= 3);
  if (words.length === 0) return [];

  const scored = FAQS.map(faq => {
    const haystack = `${faq.question} ${faq.answer}`.toLowerCase();
    let score = 0;
    for (const w of words) {
      if (faq.keywords.some(k => k.includes(w) || w.includes(k))) score += 2;
      else if (haystack.includes(w)) score += 1;
    }
    return { faq, score };
  })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map(x => x.faq);

  return limit ? scored.slice(0, limit) : scored;
}
