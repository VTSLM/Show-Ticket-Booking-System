"use client";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="min-h-[calc(100vh-64px)] flex flex-col">
      {/* Hero */}
      <section className="bg-[var(--background)] text-white py-20 px-6 text-center flex-1 flex flex-col items-center justify-center">
        <h1 className="text-5xl font-bold mb-4">
          Book Your <span className="text-[#287cff]">Perfect</span> Show
        </h1>
        <p className="text-[var(--muted)] text-lg mb-8 max-w-xl">
          Movies, concerts, theatre — all in one place. Choose your seats, pay instantly, get your e-ticket.
        </p>
        <div className="flex gap-4 flex-wrap justify-center">
          <Link href="/browse" className="btn-primary text-lg py-3 px-8">Browse Shows</Link>
          <Link
            href={user ? "/browse" : "/auth/register"}
            className="btn-secondary text-lg py-3 px-8"
          >
            {user ? "My Bookings" : "Get Started"}
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="py-16 px-6 bg-[var(--surface)]">
        <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          {[
            { icon: "🎬", title: "All Show Types", desc: "Movies, concerts, theatre and more" },
            { icon: "💺", title: "Real-time Seats", desc: "Live seat availability with WebSocket updates" },
            { icon: "🎫", title: "Instant E-Ticket", desc: "QR code + PDF ticket emailed instantly" },
          ].map(f => (
            <div key={f.title} className="card">
              <div className="text-4xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-lg mb-1">{f.title}</h3>
              <p className="text-[var(--muted)] text-sm">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
