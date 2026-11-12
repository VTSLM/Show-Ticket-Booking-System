"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { browseApi, seatsApi, bookingsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import clsx from "clsx";

type SeatStatus = "available" | "locked" | "booked" | "reserved" | "mine";

interface Seat {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: string;
  status: SeatStatus;
  price: number;
  locked_by?: string;
}

export default function SeatsPage() {
  const { showId } = useParams<{ showId: string }>();
  const router = useRouter();
  const { user, profile, loading: authLoading } = useAuth();

  const [show, setShow] = useState<any>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);

  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const loadSeats = useCallback(async () => {
    try {
      const data = await seatsApi.map(showId);

      setSeats(
        data.map((seat: any) => ({
          ...seat,
          status:
            seat.status === "locked" && seat.locked_by === profile?.id
              ? "mine"
              : seat.status,
        })),
      );
    } catch {
      toast.error("Failed to load seats");
    }
  }, [showId, profile?.id]);

  useEffect(() => {
    let isMounted = true;

    browseApi
      .showDetail(showId)
      .then((data) => {
        if (isMounted) setShow(data);
      })
      .catch(() => {
        if (isMounted) toast.error("Failed to load show details");
      });

    loadSeats().finally(() => {
      if (isMounted) setLoading(false);
    });

    let socket: WebSocket | undefined;

    try {
      const wsUrl = `${apiUrl.replace(/^http/, "ws")}/api/seats/${showId}/ws`;
      socket = new WebSocket(wsUrl);

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "lock" || message.type === "release") {
            loadSeats();
          }
        } catch {
          // ignore malformed websocket messages
        }
      };
    } catch {
      // seat map still works if websocket isn't available
    }

    return () => {
      isMounted = false;
      socket?.close();
    };
  }, [showId, apiUrl, loadSeats]);

  const toggle = async (seat: Seat) => {
    if (authLoading) return; // wait for auth to resolve
    if (!user) {
      toast.error("Please log in to select seats");
      router.push(`/auth/login?redirect=/shows/${showId}/seats`);
      return;
    }

    if (
      seat.status === "booked" ||
      seat.status === "locked" ||
      seat.status === "reserved"
    ) {
      return;
    }

    const seatId = seat.show_seat_id;

    if (selected.includes(seatId)) {
      setSelected((current) => current.filter((id) => id !== seatId));

      try {
        await seatsApi.release(showId, [seatId]);
        await loadSeats();
      } catch {
        toast.error("Could not release this seat");
      }

      return;
    }

    try {
      await seatsApi.lock(showId, [seatId]);
      setSelected((current) => [...current, seatId]);
      await loadSeats();
    } catch (error: any) {
      toast.error(error.message || "Seat is no longer available");
      await loadSeats();
    }
  };

  const handleBook = async () => {
    if (!selected.length) {
      toast.error("Select at least one seat");
      return;
    }

    setBooking(true);

    try {
      const result = (await bookingsApi.create(showId, selected)) as {
        booking_id: string;
      };

      toast.success("Booking created! Proceeding to payment...");
      router.push(`/payment?booking_id=${result.booking_id}`);
    } catch (error: any) {
      toast.error(error.message || "Booking failed");
    } finally {
      setBooking(false);
    }
  };

  const rows = seats.reduce<Record<string, Seat[]>>((result, seat) => {
    if (!result[seat.row_label]) result[seat.row_label] = [];
    result[seat.row_label].push(seat);
    return result;
  }, {});

  const seatColor = (seat: Seat) => {
    if (selected.includes(seat.show_seat_id)) {
      return "border-blue-500 bg-blue-400";
    }
    if (seat.status === "booked") {
      return "cursor-not-allowed border-gray-500 bg-gray-400";
    }
    if (seat.status === "locked") {
      return "cursor-not-allowed border-amber-500 bg-amber-300";
    }
    if (seat.status === "reserved") {
      return "cursor-not-allowed border-gray-500 bg-gray-300";
    }
    if (seat.status === "mine") {
      return "border-blue-400 bg-blue-200";
    }
    if (seat.seat_type?.toLowerCase() === "premium") {
      return "border-purple-400 bg-purple-200 hover:bg-purple-300";
    }
    return "border-emerald-500 bg-emerald-300 hover:bg-emerald-400";
  };

  const total = seats
    .filter((seat) => selected.includes(seat.show_seat_id))
    .reduce((sum, seat) => sum + Number(seat.price || 0), 0);

  if (loading) {
    return (
      <main className="min-h-screen px-4 py-20 text-center text-slate-300">
        Loading seat map…
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8 text-slate-100 sm:px-6">
      {show && (
        <section className="mb-8 rounded-2xl border border-slate-700 bg-slate-900 p-5 sm:p-6">
          <p className="mb-2 text-sm font-semibold uppercase tracking-widest text-blue-400">
            Choose your seats
          </p>
          <h1 className="text-2xl font-bold text-white">
            {show.title || show.event_title}
          </h1>
          <p className="mt-2 text-slate-300">
            {show.venue_name}
            {show.screen_name ? ` — ${show.screen_name}` : ""}
          </p>
          {show.start_time && (
            <p className="mt-1 text-sm text-slate-400">
              {new Date(show.start_time).toLocaleString("en-IN")}
            </p>
          )}
        </section>
      )}

      <section
        aria-label="Select seats in the theater"
        className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 sm:p-8"
      >
        <h2 className="mb-6 text-center text-xl font-semibold tracking-tight text-white">
          Select Your Seats
        </h2>
        <div className="overflow-x-auto pb-2">
          <div className="mx-auto w-max min-w-full px-2">
            <div
              className="cinema-screen-wrap"
              role="img"
              aria-label="Cinema screen"
            >
              <div className="cinema-screen">
                <span>SCREEN</span>
              </div>
              <div className="cinema-screen-glow" aria-hidden="true" />
            </div>

            {Object.keys(rows).length === 0 ? (
              <p className="py-12 text-center text-slate-400">
                No seats are currently available for this show.
              </p>
            ) : (
              <div className="space-y-2">
                {Object.entries(rows)
                  .sort(([first], [second]) => first.localeCompare(second))
                  .map(([row, rowSeats]) => (
                    <div
                      key={row}
                      className="flex items-center justify-center gap-2"
                    >
                      <span className="w-6 text-center text-sm font-semibold text-slate-400">
                        {row}
                      </span>

                      <div className="flex gap-2">
                        {[...rowSeats]
                          .sort((a, b) => a.seat_number - b.seat_number)
                          .map((seat) => {
                            const unavailable =
                              seat.status === "booked" ||
                              seat.status === "locked" ||
                              seat.status === "reserved";

                            return (
                              <button
                                key={seat.show_seat_id}
                                type="button"
                                onClick={() => toggle(seat)}
                                title={`${seat.row_label}${seat.seat_number} — ₹${seat.price} (${seat.status})`}
                                aria-label={`Row ${seat.row_label}, seat ${seat.seat_number}, ₹${seat.price}`}
                                aria-pressed={selected.includes(seat.show_seat_id)}
                                disabled={unavailable}
                                className={clsx(
                                  "flex h-9 w-9 items-center justify-center rounded-t-lg rounded-b-md border text-xs font-bold text-black transition-colors",
                                  seatColor(seat),
                                )}
                              >
                                {seat.seat_number}
                              </button>
                            );
                          })}
                      </div>

                      <span className="w-6 text-center text-sm font-semibold text-slate-400">
                        {row}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-3 border-t border-slate-800 pt-5 text-sm text-slate-300">
          {[
            ["bg-emerald-300", "Available"],
            ["bg-blue-400", "Selected"],
            ["bg-amber-300", "Locked"],
            ["bg-gray-400", "Booked"],
            ["bg-purple-200", "Premium"],
          ].map(([color, label]) => (
            <span key={label} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={`h-4 w-4 rounded border border-black/20 ${color}`}
              />
              {label}
            </span>
          ))}
        </div>
      </section>

      {selected.length > 0 && (
        <section className="mt-6 flex flex-col gap-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-white">
              {selected.length} seat{selected.length === 1 ? "" : "s"} selected
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Total:{" "}
              <span className="font-bold text-blue-400">
                ₹{total.toLocaleString("en-IN")}
              </span>
            </p>
          </div>

          <button
            type="button"
            onClick={handleBook}
            disabled={booking}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {booking ? "Processing…" : "Proceed to Payment"}
          </button>
        </section>
      )}
    </main>
  );
}