"use client";

import { BookingConfirmation } from "@/types/booking";

interface Props {
  data: BookingConfirmation;
}

export default function TicketCard({ data }: Props) {
  const { event, seats, total_amount, booking_id, qr_code_base64, user } = data;

  return (
    <div className="relative w-full max-w-lg mx-auto">
      {/* Main ticket card */}
      <div
        className="rounded-2xl overflow-hidden shadow-2xl"
        style={{ background: "linear-gradient(145deg, #1E293B 0%, #0F172A 100%)" }}
      >
        {/* Blue header */}
        <div className="bg-blue-600 px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-200 text-xs font-semibold tracking-widest uppercase">
                TicketFlow
              </p>
              <h2 className="text-white text-xl font-bold mt-0.5">{event.name}</h2>
            </div>
            {/* Checkmark badge */}
            <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>
        </div>

        {/* Details grid */}
        <div className="px-6 py-5 grid grid-cols-2 gap-5">
          <div>
            <p className="text-slate-400 text-[10px] uppercase tracking-widest">Date</p>
            <p className="text-white font-semibold mt-0.5">{event.date}</p>
          </div>
          <div>
            <p className="text-slate-400 text-[10px] uppercase tracking-widest">Time</p>
            <p className="text-white font-semibold mt-0.5">{event.time}</p>
          </div>
          <div className="col-span-2">
            <p className="text-slate-400 text-[10px] uppercase tracking-widest">Venue</p>
            <p className="text-white font-semibold mt-0.5">{event.venue}</p>
          </div>
        </div>

        {/* Perforation / tear line */}
        <div className="relative flex items-center px-0">
          <div className="w-5 h-5 rounded-full bg-[#0D0D0F] -ml-2.5 flex-shrink-0" />
          <div className="flex-1 border-t-2 border-dashed border-slate-700 mx-1" />
          <div className="w-5 h-5 rounded-full bg-[#0D0D0F] -mr-2.5 flex-shrink-0" />
        </div>

        {/* Seats + QR lower half */}
        <div className="px-6 py-5 flex gap-5 items-start">
          {/* Seat info */}
          <div className="flex-1">
            <p className="text-slate-400 text-[10px] uppercase tracking-widest mb-2">Seat(s)</p>
            {seats.map((s) => (
              <div
                key={s.seat_id}
                className="flex items-center justify-between bg-slate-800/60 rounded-lg px-3 py-2 mb-2"
              >
                <div>
                  <span className="text-white font-semibold text-sm">
                    Row {s.row} · #{s.number}
                  </span>
                  <span className="ml-2 text-blue-400 text-xs font-medium bg-blue-900/40 px-2 py-0.5 rounded-full">
                    {s.tier}
                  </span>
                </div>
                <span className="text-slate-300 text-sm">₹{s.price}</span>
              </div>
            ))}
            <div className="mt-3 flex items-center justify-between">
              <span className="text-slate-400 text-xs">Total Paid</span>
              <span className="text-blue-400 font-bold text-lg">₹{total_amount}</span>
            </div>
            <div className="mt-3">
              <p className="text-slate-400 text-[10px] uppercase tracking-widest">Booking ID</p>
              <p className="text-slate-300 font-mono text-xs mt-0.5">{booking_id}</p>
            </div>
          </div>

          {/* QR Code */}
          <div className="flex flex-col items-center flex-shrink-0">
            <div className="bg-white p-2 rounded-xl">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${qr_code_base64}`}
                alt="Entry QR Code"
                width={120}
                height={120}
              />
            </div>
            <p className="text-slate-500 text-[9px] text-center mt-1.5 max-w-[100px] leading-tight">
              Scan at entry
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-slate-900/60 px-6 py-3">
          <p className="text-slate-500 text-[10px] text-center">
            Ticket for {user.name} · {user.email}
          </p>
        </div>
      </div>
    </div>
  );
}
