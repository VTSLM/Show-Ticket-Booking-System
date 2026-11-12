"use client";
import { useState, useEffect } from "react";
import { managerApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";

type Tab = "shows" | "events" | "venues";

/* ── tiny helpers ───────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
  const isPublished = status === "published";
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: "0.06em",
      background: isPublished ? "#00c97722" : "#ffb30022",
      color: isPublished ? "#00c977" : "#ffb300",
      border: `1px solid ${isPublished ? "#00c97744" : "#ffb30044"}`,
    }}>
      {status.toUpperCase()}
    </span>
  );
}

function ShowStatusHint({ eventStatus }: { eventStatus: string }) {
  if (eventStatus === "published") return null;
  return (
    <span
      title="This show won't appear on Browse until the event is Published"
      style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        fontSize: 11, color: "#ffb300", cursor: "default",
      }}
    >
      ⚠ Hidden from Browse
    </span>
  );
}

export default function ManagerPage() {
  const { isManager, loading: authLoading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("shows");
  const [shows, setShows] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [venues, setVenues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const [newEvent, setNewEvent] = useState({ title: "", event_type: "movie", language: "", duration_minutes: "" });
  const [newVenue, setNewVenue] = useState({ name: "", city: "", address: "" });
  const [newShow, setNewShow] = useState({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "" });
  const [screens, setScreens] = useState<any[]>([]);
  const [selectedVenueId, setSelectedVenueId] = useState("");
  const [newScreen, setNewScreen] = useState({ name: "", rows: "", cols: "" });

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

  // Build a quick event map for the shows tab
  const eventMap = Object.fromEntries(events.map(ev => [ev.id, ev]));

  const loadScreens = async (venueId: string) => {
    if (!venueId) { setScreens([]); return; }
    try {
      setScreens(await managerApi.screens(venueId));
    } catch (err: any) {
      toast.error(err.message || "Could not load screens");
      setScreens([]);
    }
  };

  const createEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createEvent({ ...newEvent, duration_minutes: parseInt(newEvent.duration_minutes) || undefined });
      setEvents(await managerApi.events());
      setNewEvent({ title: "", event_type: "movie", language: "", duration_minutes: "" });
      toast.success("Event created (draft) — publish it to make shows visible on Browse.");
    } catch (err: any) { toast.error(err.message); }
  };

  const togglePublish = async (ev: any) => {
    const nextStatus = ev.status === "published" ? "draft" : "published";
    setTogglingId(ev.id);
    try {
      const updated = await managerApi.updateEvent(ev.id, { status: nextStatus });
      setEvents(evts => evts.map(e => e.id === ev.id ? updated : e));
      toast.success(nextStatus === "published"
        ? `"${ev.title}" is now live on Browse!`
        : `"${ev.title}" moved back to draft.`);
    } catch (err: any) {
      toast.error(err.message || "Could not update event");
    } finally {
      setTogglingId(null);
    }
  };

  const createVenue = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createVenue(newVenue);
      setVenues(await managerApi.venues());
      setNewVenue({ name: "", city: "", address: "" });
      toast.success("Venue created!");
    } catch (err: any) { toast.error(err.message); }
  };

  const createScreen = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVenueId) { toast.error("Please select a venue"); return; }
    const rows = parseInt(newScreen.rows);
    const cols = parseInt(newScreen.cols);
    if (!rows || !cols || rows <= 0 || cols <= 0) { toast.error("Rows and columns must be > 0"); return; }
    try {
      await managerApi.createScreen(selectedVenueId, { name: newScreen.name, capacity: rows * cols, rows, cols });
      setScreens(await managerApi.screens(selectedVenueId));
      setNewScreen({ name: "", rows: "", cols: "" });
      toast.success(`Screen created with ${rows * cols} seats!`);
    } catch (err: any) { toast.error(err.message || "Could not create screen"); }
  };

  const createShow = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createShow({ ...newShow, base_price: parseFloat(newShow.base_price) });
      setShows(await managerApi.shows());
      setNewShow({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "" });
      toast.success("Show created!");
    } catch (err: any) { toast.error(err.message); }
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

      {/* ── SHOWS TAB ── */}
      {tab === "shows" && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Create Show</h2>
            <form onSubmit={createShow} className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Event</label>
                <select className="input text-sm" value={newShow.event_id}
                  onChange={e => setNewShow(s => ({ ...s, event_id: e.target.value }))} required>
                  <option value="">Select event</option>
                  {events.map(ev => (
                    <option key={ev.id} value={ev.id}>
                      {ev.title}{ev.status !== "published" ? " (draft)" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Screen</label>
                <select className="input text-sm" value={newShow.screen_id}
                  onChange={e => setNewShow(s => ({ ...s, screen_id: e.target.value }))} required>
                  <option value="">Select screen</option>
                  {screens.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
                </select>
              </div>
              {inp("Start Time", newShow.start_time, (e: any) => setNewShow(s => ({ ...s, start_time: e.target.value })), "datetime-local")}
              {inp("End Time", newShow.end_time, (e: any) => setNewShow(s => ({ ...s, end_time: e.target.value })), "datetime-local")}
              {inp("Base Price (₹)", newShow.base_price, (e: any) => setNewShow(s => ({ ...s, base_price: e.target.value })), "number")}
              <div className="col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Load screens for venue</label>
                <select className="input text-sm" onChange={e => loadScreens(e.target.value)}>
                  <option value="">Select venue to load screens</option>
                  {venues.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </div>
              <button type="submit" className="col-span-2 btn-primary">Create Show</button>
            </form>
          </div>

          <div className="card">
            <h2 className="font-semibold text-lg mb-4">All Shows ({shows.length})</h2>
            <div className="space-y-2">
              {shows.map(s => {
                const parentEvent = eventMap[s.event_id];
                return (
                  <div key={s.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium">{s.event_title}</p>
                        {parentEvent && <ShowStatusHint eventStatus={parentEvent.status} />}
                      </div>
                      <p className="text-sm text-gray-500">{s.venue_name} — {s.screen_name}</p>
                      <p className="text-sm text-gray-500">{new Date(s.start_time).toLocaleString("en-IN")}</p>
                    </div>
                    <div className="flex gap-2 items-center">
                      <span className="text-red-500 font-bold">₹{s.base_price}</span>
                      <button onClick={() => deleteShow(s.id)} className="text-red-400 hover:text-red-600 text-sm">Delete</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── EVENTS TAB ── */}
      {tab === "events" && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Create Event</h2>
            <p className="text-xs text-gray-400 mb-3">
              Events are saved as <strong>Draft</strong> by default. Use the Publish button on each event to make its shows visible on Browse.
            </p>
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
              <button type="submit" className="col-span-2 btn-primary">Create Event (Draft)</button>
            </form>
          </div>

          <div className="card">
            <h2 className="font-semibold text-lg mb-4">Events ({events.length})</h2>
            {events.length === 0 && (
              <p className="text-sm text-gray-500">No events yet. Create one above.</p>
            )}
            <div className="grid grid-cols-1 gap-3">
              {events.map(ev => (
                <div key={ev.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "14px 16px",
                    borderRadius: 12,
                    background: "var(--surface-raised, #f9f9f9)",
                    border: "1px solid var(--border, #e5e7eb)",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600, fontSize: 15 }}>{ev.title}</span>
                      <StatusBadge status={ev.status} />
                    </div>
                    <p style={{ fontSize: 13, color: "var(--muted, #9ca3af)", margin: 0 }}>
                      {ev.event_type}{ev.language ? ` · ${ev.language}` : ""}{ev.duration_minutes ? ` · ${ev.duration_minutes} min` : ""}
                    </p>
                    {ev.status === "draft" && (
                      <p style={{ fontSize: 12, color: "#ffb300", marginTop: 4 }}>
                        ⚠ Shows for this event won't appear on Browse until published.
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => togglePublish(ev)}
                    disabled={togglingId === ev.id}
                    style={{
                      padding: "8px 18px",
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 700,
                      cursor: togglingId === ev.id ? "not-allowed" : "pointer",
                      opacity: togglingId === ev.id ? 0.6 : 1,
                      transition: "all 0.15s",
                      border: ev.status === "published"
                        ? "1.5px solid #ff334440"
                        : "1.5px solid #00c97744",
                      background: ev.status === "published"
                        ? "#ff334410"
                        : "#00c97710",
                      color: ev.status === "published" ? "#ff5566" : "#00c977",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {togglingId === ev.id
                      ? "..."
                      : ev.status === "published" ? "Unpublish" : "Publish"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── VENUES TAB ── */}
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
              <label className="block text-xs text-gray-500 mb-1">Select Venue</label>
              <select className="input text-sm" value={selectedVenueId}
                onChange={async (e) => { setSelectedVenueId(e.target.value); await loadScreens(e.target.value); }}>
                <option value="">Select venue</option>
                {venues.map(v => <option key={v.id} value={v.id}>{v.name} — {v.city}</option>)}
              </select>
            </div>
            {selectedVenueId && (
              <>
                <form onSubmit={createScreen} className="grid grid-cols-2 gap-3 mb-6">
                  {inp("Screen Name", newScreen.name, (e: any) => setNewScreen(s => ({ ...s, name: e.target.value })))}
                  {inp("Rows", newScreen.rows, (e: any) => setNewScreen(s => ({ ...s, rows: e.target.value })), "number")}
                  {inp("Columns", newScreen.cols, (e: any) => setNewScreen(s => ({ ...s, cols: e.target.value })), "number")}
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Capacity</label>
                    <div className="input text-sm bg-gray-100">
                      {(parseInt(newScreen.rows)||0)*(parseInt(newScreen.cols)||0)} seats
                    </div>
                  </div>
                  <button type="submit" className="col-span-2 btn-primary">Create Screen</button>
                </form>
                <h3 className="font-medium mb-3">Screens</h3>
                {screens.length === 0 ? (
                  <p className="text-sm text-gray-500">No screens for this venue yet.</p>
                ) : (
                  <div className="space-y-2">
                    {screens.map(sc => (
                      <div key={sc.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                        <div>
                          <p className="font-medium">{sc.name}</p>
                          <p className="text-sm text-gray-500">Capacity: {sc.capacity} seats</p>
                          <p className="text-xs text-gray-400">Screen ID: {sc.id}</p>
                        </div>
                        <span className="text-sm text-green-600 font-medium">Active</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
