"use client";
import { useState, useEffect, useCallback, useRef } from "react";
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
  const { user, profile } = useAuth();
  const [show, setShow] = useState<any>(null);
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const loadSeats = useCallback(async () => {
    try {
      const data = await seatsApi.map(showId);
      setSeats(data.map((s: any) => ({
        ...s,
        status: s.status === "locked" && s.locked_by === profile?.id ? "mine" : s.status
      })));
    } catch (e: any) {
      toast.error("Failed to load seats");
    }
  }, [showId, profile?.id]);

  useEffect(() => {
    browseApi.showDetail(showId).then(setShow).catch(() => {});
    loadSeats().finally(() => setLoading(false));

    // WebSocket for real-time updates
    const wsUrl = API_URL.replace("http", "ws") + `/api/seats/${showId}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "lock" || msg.type === "release") loadSeats();
      } catch {}
    };
    return () => { ws.close(); };
  }, [showId]);

  const toggle = async (seat: Seat) => {
    if (!user) { toast.error("Please login first"); router.push("/auth/login"); return; }
    if (seat.status === "booked" || seat.status === "locked") return;

    if (selected.includes(seat.show_seat_id)) {
      // Deselect — release lock
      const newSel = selected.filter(id => id !== seat.show_seat_id);
      setSelected(newSel);
      try {
        await seatsApi.release(showId, [seat.show_seat_id]);
      } catch {}
    } else {
      // Select — lock
      const newSel = [...selected, seat.show_seat_id];
      try {
        await seatsApi.lock(showId, [seat.show_seat_id]);
        setSelected(newSel);
        await loadSeats();
      } catch (e: any) {
        toast.error(e.message || "Seat no longer available");
        await loadSeats();
      }
    }
  };

  const handleBook = async () => {
    if (!selected.length) { toast.error("Select at least one seat"); return; }
    setBooking(true);
    try {
      const res = await bookingsApi.create(showId, selected) as any;
      toast.success("Booking created! Proceeding to payment...");
      router.push(`/payment?booking_id=${res.booking_id}`);
    } catch (e: any) {
      toast.error(e.message || "Booking failed");
    } finally {
      setBooking(false);
    }
  };

  const rows = seats.reduce((acc, s) => {
    if (!acc[s.row_label]) acc[s.row_label] = [];
    acc[s.row_label].push(s);
    return acc;
  }, {} as Record<string, Seat[]>);

  const seatColor = (s: Seat) => {
    if (selected.includes(s.show_seat_id)) return "bg-blue-500 text-white";
    if (s.status === "booked") return "bg-gray-400 text-white cursor-not-allowed";
    if (s.status === "locked") return "bg-yellow-400 text-white cursor-not-allowed";
    if (s.status === "mine") return "bg-blue-300 text-white";
    if (s.seat_type === "premium") return "bg-purple-100 hover:bg-purple-200 border-purple-400";
    return "bg-green-100 hover:bg-green-200 border-green-400";
  };

  const total = seats.filter(s => selected.includes(s.show_seat_id)).reduce((a, s) => a + s.price, 0);

  if (loading) return <div className="text-center py-20 text-gray-400">Loading seat map...</div>;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {show && (
        <div className="card mb-6">
          <h1 className="text-2xl font-bold">{show.title || show.event_title}</h1>
          <p className="text-gray-500">{show.venue_name} — {show.screen_name}</p>
          <p className="text-gray-500">{show.start_time ? new Date(show.start_time).toLocaleString("en-IN") : ""}</p>
        </div>
      )}

      {/* Screen indicator */}
      <div className="text-center mb-6">
        <div className="inline-block bg-gray-800 text-white text-sm px-16 py-1 rounded-full">SCREEN</div>
      </div>

      {/* Seat grid */}
      <div className="card overflow-x-auto">
        {Object.entries(rows).sort(([a],[b]) => a.localeCompare(b)).map(([row, rowSeats]) => (
          <div key={row} className="flex items-center gap-1 mb-1">
            <span className="w-6 text-center text-sm font-bold text-gray-500">{row}</span>
            <div className="flex gap-1 flex-wrap">
              {rowSeats.sort((a,b) => a.seat_number - b.seat_number).map(s => (
                <button key={s.show_seat_id}
                  onClick={() => toggle(s)}
                  title={`${s.row_label}${s.seat_number} — ₹${s.price} (${s.status})`}
                  className={clsx("w-8 h-8 text-xs rounded border font-mono transition-all", seatColor(s))}
                  disabled={s.status === "booked" || (s.status === "locked" && !selected.includes(s.show_seat_id))}>
                  {s.seat_number}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-4 flex-wrap text-xs mt-3 text-gray-600">
        {[["bg-green-100 border border-green-400","Available"],["bg-blue-500","Selected"],
          ["bg-yellow-400","Locked"],["bg-gray-400","Booked"],["bg-purple-100 border border-purple-400","Premium"]
        ].map(([cls,label]) => (
          <span key={label} className="flex items-center gap-1">
            <span className={`w-4 h-4 rounded ${cls}`} />{label}
          </span>
        ))}
      </div>

      {/* Booking summary */}
      {selected.length > 0 && (
        <div className="mt-6 card flex items-center justify-between">
          <div>
            <p className="font-semibold">{selected.length} seat(s) selected</p>
            <p className="text-gray-500 text-sm">Total: <span className="font-bold text-red-500">₹{total}</span></p>
          </div>
          <button onClick={handleBook} disabled={booking} className="btn-primary">
            {booking ? "Processing..." : "Proceed to Payment"}
          </button>
        </div>
      )}
    </div>
  );
}
