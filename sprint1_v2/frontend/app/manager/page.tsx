"use client";
import { useState, useEffect } from "react";
import { managerApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";

type Tab = "shows" | "events" | "venues";

export default function ManagerPage() {
  const { isManager, loading: authLoading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("shows");
  const [shows, setShows] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [venues, setVenues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Create state
  const [newEvent, setNewEvent] = useState({ title: "", event_type: "movie", language: "", duration_minutes: "" });
  const [newVenue, setNewVenue] = useState({ name: "", city: "", address: "" });
  const [newShow, setNewShow] = useState({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "" });
  const [showVenueId, setShowVenueId] = useState("");
  const [showScreens, setShowScreens] = useState<any[]>([]);
  const [endTimeTouched, setEndTimeTouched] = useState(false);
  const [creatingShow, setCreatingShow] = useState(false);
  const [screens, setScreens] = useState<any[]>([]);
  const [selectedVenueId, setSelectedVenueId] = useState("");
  const [newScreen, setNewScreen] = useState({
    name: "",
    rows: "",
    cols: "",
  });

  useEffect(() => {
    if (!authLoading && !isManager) { router.push("/"); return; }
    if (!authLoading && isManager) {
      Promise.all([
        managerApi.shows().then(setShows),
        managerApi.events().then(setEvents),
        managerApi.venues().then(setVenues),
      ]).finally(() => setLoading(false));
    }
  }, [isManager, authLoading]);

  const loadScreens = async (venueId: string) => {
    if (!venueId) {
      setScreens([]);
      return;
    }

    try {
      const data = await managerApi.screens(venueId);
      setScreens(data);
    } catch (err: any) {
      toast.error(err.message || "Could not load screens");
      setScreens([]);
    }
  };

  const loadShowScreens = async (venueId: string) => {
    setShowVenueId(venueId);
    setNewShow(s => ({ ...s, screen_id: "" }));
    if (!venueId) {
      setShowScreens([]);
      return;
    }
    try {
      const data = await managerApi.screens(venueId);
      setShowScreens(data);
    } catch (err: any) {
      toast.error(err.message || "Could not load screens");
      setShowScreens([]);
    }
  };

  const parseLocalDateTime = (val: string): Date | null => {
    if (!val) return null;
    const [datePart, timePart] = val.split("T");
    if (!datePart || !timePart) return null;
    const [y, m, d] = datePart.split("-").map(Number);
    const [hh, mm] = timePart.split(":").map(Number);
    if ([y, m, d, hh, mm].some(Number.isNaN)) return null;
    return new Date(y, m - 1, d, hh, mm, 0, 0);
  };

  const formatLocalDateTime = (date: Date): string => {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const computeDefaultEndTime = (startVal: string, eventId: string): string => {
    const startDate = parseLocalDateTime(startVal);
    if (!startDate) return "";
    const ev = events.find(item => item.id === eventId);
    const durationMins = Number(ev?.duration_minutes) > 0 ? Number(ev.duration_minutes) : 120;
    return formatLocalDateTime(new Date(startDate.getTime() + (durationMins + 15) * 60_000));
  };

  const createEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createEvent({ ...newEvent, duration_minutes: parseInt(newEvent.duration_minutes) || undefined });
      const evts = await managerApi.events();
      setEvents(evts);
      setNewEvent({ title: "", event_type: "movie", language: "", duration_minutes: "" });
      toast.success("Event created!");
    } catch (err: any) { toast.error(err.message); }
  };

  const createVenue = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createVenue(newVenue);
      const vs = await managerApi.venues();
      setVenues(vs);
      setNewVenue({ name: "", city: "", address: "" });
      toast.success("Venue created!");
    } catch (err: any) { toast.error(err.message); }
  };

  const createScreen = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedVenueId) {
      toast.error("Please select a venue");
      return;
    }

    const rows = parseInt(newScreen.rows);
    const cols = parseInt(newScreen.cols);

    if (!rows || !cols || rows <= 0 || cols <= 0) {
      toast.error("Rows and columns must be greater than 0");
      return;
    }

    const capacity = rows * cols;

    try {
      await managerApi.createScreen(selectedVenueId, {
        name: newScreen.name,
        capacity,
        rows,
        cols,
      });

      const updatedScreens = await managerApi.screens(selectedVenueId);
      setScreens(updatedScreens);
      if (showVenueId === selectedVenueId) {
        setShowScreens(updatedScreens);
      }

      setNewScreen({
        name: "",
        rows: "",
        cols: "",
      });

      toast.success(`Screen created with ${capacity} seats!`);
    } catch (err: any) {
      toast.error(err.message || "Could not create screen");
    }
  };
  const createShow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newShow.event_id) {
      toast.error("Please select an event.");
      return;
    }
    if (!showVenueId || !newShow.screen_id) {
      toast.error("Please select a venue and screen.");
      return;
    }
    const startDate = parseLocalDateTime(newShow.start_time);
    const endDate = parseLocalDateTime(newShow.end_time);
    if (!startDate || !endDate) {
      toast.error("Please select valid start and end times.");
      return;
    }
    if (endDate.getTime() <= startDate.getTime()) {
      toast.error("Show end time must be strictly after start time.");
      return;
    }
    const basePrice = parseFloat(newShow.base_price);
    if (Number.isNaN(basePrice) || basePrice <= 0) {
      toast.error("Base price must be greater than 0.");
      return;
    }

    setCreatingShow(true);
    try {
      await managerApi.createShow({
        event_id: newShow.event_id,
        screen_id: newShow.screen_id,
        start_time: startDate.toISOString(),
        end_time: endDate.toISOString(),
        base_price: basePrice,
      });
      const ss = await managerApi.shows();
      setShows(ss);
      setNewShow({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "" });
      setShowVenueId("");
      setShowScreens([]);
      setEndTimeTouched(false);
      toast.success("Show created!");
    } catch (err: any) {
      toast.error(err.message || "Failed to create show");
    } finally {
      setCreatingShow(false);
    }
  };

  const deleteShow = async (id: string) => {
    if (!confirm("Delete this show?")) return;
    try {
      await managerApi.deleteShow(id);
      setShows(ss => ss.filter(s => s.id !== id));
      toast.success("Deleted");
    } catch (err: any) { toast.error(err.message); }
  };

  if (authLoading || loading) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  const startParsed = parseLocalDateTime(newShow.start_time);
  const endParsed = parseLocalDateTime(newShow.end_time);
  const invalidTimeRange = Boolean(startParsed && endParsed && endParsed.getTime() <= startParsed.getTime());

  const inp = (label: string, val: string, onChange: any, type = "text", required = true) => (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input className="input text-sm" type={type} value={val} onChange={onChange} required={required} />
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Manager Dashboard</h1>
      <div className="flex gap-2 mb-6">
        {(["shows","events","venues"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg font-medium text-sm transition ${tab===t ? "bg-[#1a1a2e] text-white" : "bg-white text-gray-600 hover:bg-gray-100"}`}>
            {t.charAt(0).toUpperCase()+t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "shows" && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Create Show</h2>
            <form onSubmit={createShow} className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Event</label>
                <select
                  className="input text-sm"
                  value={newShow.event_id}
                  onChange={e => {
                    const eventId = e.target.value;
                    setNewShow(s => {
                      const nextEnd = s.start_time && !endTimeTouched
                        ? computeDefaultEndTime(s.start_time, eventId)
                        : s.end_time;
                      return { ...s, event_id: eventId, end_time: nextEnd };
                    });
                  }}
                  required
                >
                  <option value="">Select event</option>
                  {events.map(ev => (
                    <option key={ev.id} value={ev.id}>
                      {ev.title}{ev.duration_minutes ? ` (${ev.duration_minutes} min)` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Venue</label>
                <select
                  className="input text-sm"
                  value={showVenueId}
                  onChange={e => loadShowScreens(e.target.value)}
                  required
                >
                  <option value="">Select venue</option>
                  {venues.map(v => <option key={v.id} value={v.id}>{v.name} — {v.city}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Screen</label>
                <select
                  className="input text-sm"
                  value={newShow.screen_id}
                  disabled={!showVenueId}
                  onChange={e => setNewShow(s => ({ ...s, screen_id: e.target.value }))}
                  required
                >
                  <option value="">
                    {!showVenueId
                      ? "Select venue first"
                      : showScreens.length === 0
                        ? "No screens in this venue"
                        : "Select screen"}
                  </option>
                  {showScreens.map(sc => (
                    <option key={sc.id} value={sc.id}>
                      {sc.name} ({sc.capacity} seats)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Base Price (₹)</label>
                <input
                  className="input text-sm"
                  type="number"
                  min="1"
                  step="0.01"
                  value={newShow.base_price}
                  onChange={e => setNewShow(s => ({ ...s, base_price: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Start Time</label>
                <input
                  className="input text-sm"
                  type="datetime-local"
                  value={newShow.start_time}
                  onChange={e => {
                    const startVal = e.target.value;
                    setNewShow(s => {
                      const sp = parseLocalDateTime(startVal);
                      const ep = parseLocalDateTime(s.end_time);
                      const shouldAutoFill =
                        Boolean(startVal) && (!endTimeTouched || !ep || (sp !== null && ep.getTime() <= sp.getTime()));
                      return {
                        ...s,
                        start_time: startVal,
                        end_time: shouldAutoFill ? computeDefaultEndTime(startVal, s.event_id) : s.end_time,
                      };
                    });
                  }}
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">End Time</label>
                <input
                  className="input text-sm"
                  type="datetime-local"
                  min={newShow.start_time || undefined}
                  value={newShow.end_time}
                  onChange={e => {
                    setEndTimeTouched(true);
                    setNewShow(s => ({ ...s, end_time: e.target.value }));
                  }}
                  required
                />
              </div>
              {invalidTimeRange && (
                <p className="col-span-2 text-xs text-red-600">
                  Show end time must be strictly after start time.
                </p>
              )}
              <button type="submit" disabled={creatingShow} className="col-span-2 btn-primary disabled:opacity-60">
                {creatingShow ? "Creating Show..." : "Create Show"}
              </button>
            </form>
          </div>
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">All Shows ({shows.length})</h2>
            <div className="space-y-2">
              {shows.map(s => (
                <div key={s.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">{s.event_title}</p>
                    <p className="text-sm text-gray-500">{s.venue_name} — {s.screen_name}</p>
                    <p className="text-sm text-gray-500">
                      {new Date(s.start_time).toLocaleString("en-IN")}
                      {s.end_time ? ` – ${new Date(s.end_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2 items-center">
                    <span className="text-red-500 font-bold">₹{s.base_price}</span>
                    <button onClick={() => deleteShow(s.id)} className="text-red-400 hover:text-red-600 text-sm">Delete</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "events" && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Create Event</h2>
            <form onSubmit={createEvent} className="grid grid-cols-2 gap-3">
              {inp("Title", newEvent.title, (e: any) => setNewEvent(v => ({ ...v, title: e.target.value })))}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Type</label>
                <select className="input text-sm" value={newEvent.event_type}
                  onChange={e => setNewEvent(v => ({ ...v, event_type: e.target.value }))}>
                  {["movie","concert","theatre","other"].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              {inp("Language", newEvent.language, (e: any) => setNewEvent(v => ({ ...v, language: e.target.value })), "text", false)}
              {inp("Duration (min)", newEvent.duration_minutes, (e: any) => setNewEvent(v => ({ ...v, duration_minutes: e.target.value })), "number", false)}
              <button type="submit" className="col-span-2 btn-primary">Create Event</button>
            </form>
          </div>
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Events ({events.length})</h2>
            <div className="grid grid-cols-2 gap-3">
              {events.map(ev => (
                <div key={ev.id} className="p-3 bg-gray-50 rounded-lg">
                  <p className="font-medium">{ev.title}</p>
                  <p className="text-sm text-gray-500">{ev.event_type} • {ev.language || "—"}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${ev.status==="published"?"bg-green-100 text-green-700":"bg-gray-100 text-gray-600"}`}>{ev.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "venues" && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Create Venue</h2>
            <form onSubmit={createVenue} className="grid grid-cols-2 gap-3">
              {inp("Name", newVenue.name, (e: any) => setNewVenue(v => ({ ...v, name: e.target.value })))}
              {inp("City", newVenue.city, (e: any) => setNewVenue(v => ({ ...v, city: e.target.value })))}
              {inp("Address", newVenue.address, (e: any) => setNewVenue(v => ({ ...v, address: e.target.value })), "text", false)}
              <button type="submit" className="col-span-2 btn-primary">Create Venue</button>
            </form>
          </div>
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Venues ({venues.length})</h2>
            <div className="grid grid-cols-2 gap-3">
              {venues.map(v => (
                <div key={v.id} className="p-3 bg-gray-50 rounded-lg">
                  <p className="font-medium">{v.name}</p>
                  <p className="text-sm text-gray-500">{v.city}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Manage Screens</h2>

            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1">
                Select Venue
              </label>

              <select
                className="input text-sm"
                value={selectedVenueId}
                onChange={async (e) => {
                  const venueId = e.target.value;
                  setSelectedVenueId(venueId);
                  await loadScreens(venueId);
                }}
              >
                <option value="">Select venue</option>

                {venues.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.name} — {v.city}
                  </option>
                ))}
              </select>
            </div>

            {selectedVenueId && (
              <>
                <form
                  onSubmit={createScreen}
                  className="grid grid-cols-2 gap-3 mb-6"
                >
                  {inp(
                    "Screen Name",
                    newScreen.name,
                    (e: any) =>
                      setNewScreen(s => ({
                        ...s,
                        name: e.target.value
                      }))
                  )}

                  {inp(
                    "Rows",
                    newScreen.rows,
                    (e: any) =>
                      setNewScreen(s => ({
                        ...s,
                        rows: e.target.value
                      })),
                    "number"
                  )}

                  {inp(
                    "Columns",
                    newScreen.cols,
                    (e: any) =>
                      setNewScreen(s => ({
                        ...s,
                        cols: e.target.value
                      })),
                    "number"
                  )}

                  <div>
                    <label className="block text-xs text-gray-500 mb-1">
                      Capacity
                    </label>

                    <div className="input text-sm bg-gray-100">
                      {(parseInt(newScreen.rows) || 0) *
                        (parseInt(newScreen.cols) || 0)} seats
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="col-span-2 btn-primary"
                  >
                    Create Screen
                  </button>
                </form>

                <div>
                  <h3 className="font-medium mb-3">
                    Screens
                  </h3>

                  {screens.length === 0 ? (
                    <p className="text-sm text-gray-500">
                      No screens created for this venue yet.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {screens.map(sc => (
                        <div
                          key={sc.id}
                          className="flex justify-between items-center p-3 bg-gray-50 rounded-lg"
                        >
                          <div>
                            <p className="font-medium">
                              {sc.name}
                            </p>

                            <p className="text-sm text-gray-500">
                              Capacity: {sc.capacity} seats
                            </p>

                            <p className="text-xs text-gray-400">
                              Screen ID: {sc.id}
                            </p>
                          </div>

                          <span className="text-sm text-green-600 font-medium">
                            Active
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
