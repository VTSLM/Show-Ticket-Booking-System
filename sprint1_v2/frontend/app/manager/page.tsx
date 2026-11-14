"use client";
import { useState, useEffect } from "react";
import { managerApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";

type Tab = "shows" | "events" | "venues";

/* ── Design tokens (inline — no globals needed) ── */
const C = {
  bg:        "#090b12",
  surface:   "#11141e",
  raised:    "#181c28",
  border:    "#292e3d",
  blue:      "#287cff",
  fg:        "#f4f6fb",
  muted:     "#9ba3b5",
  green:     "#00c977",
  amber:     "#ffb300",
  red:       "#ff4455",
};

/* ── Tiny helpers ── */
function Badge({ status }: { status: string }) {
  const pub = status === "published";
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 10px",
      borderRadius: 999,
      fontSize: 10,
      fontWeight: 800,
      letterSpacing: "0.1em",
      textTransform: "uppercase" as const,
      background: pub ? `${C.green}18` : `${C.amber}18`,
      color: pub ? C.green : C.amber,
      border: `1px solid ${pub ? C.green + "44" : C.amber + "44"}`,
      flexShrink: 0,
    }}>
      {pub ? "Published" : "Draft"}
    </span>
  );
}

function HiddenHint({ eventStatus }: { eventStatus: string }) {
  if (eventStatus === "published") return null;
  return (
    <span style={{ fontSize: 11, color: C.amber, display: "inline-flex", alignItems: "center", gap: 4 }}>
      ⚠ Hidden from Browse
    </span>
  );
}

function SectionCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: 16,
      padding: "24px",
      ...style,
    }}>
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{ fontSize: 15, fontWeight: 700, color: C.fg, margin: "0 0 20px", letterSpacing: "-0.01em" }}>
      {children}
    </h2>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: C.muted, marginBottom: 6, letterSpacing: "0.06em", textTransform: "uppercase" as const }}>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: C.raised,
  border: `1px solid ${C.border}`,
  borderRadius: 10,
  color: C.fg,
  padding: "10px 13px",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      {children}
    </div>
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

  const eventMap = Object.fromEntries(events.map(ev => [ev.id, ev]));

  const loadScreens = async (venueId: string) => {
    if (!venueId) { setScreens([]); return; }
    try { setScreens(await managerApi.screens(venueId)); }
    catch (err: any) { toast.error(err.message || "Could not load screens"); setScreens([]); }
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
      toast.success(nextStatus === "published" ? `"${ev.title}" is now live!` : `"${ev.title}" moved to draft.`);
    } catch (err: any) { toast.error(err.message || "Could not update event"); }
    finally { setTogglingId(null); }
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

  if (authLoading || loading) {
    return (
      <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16, color: C.muted }}>
        <div style={{ width: 36, height: 36, border: `3px solid ${C.border}`, borderTopColor: C.blue, borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        Loading…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "shows", label: "Shows", count: shows.length },
    { key: "events", label: "Events", count: events.length },
    { key: "venues", label: "Venues", count: venues.length },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.fg }}>
      {/* ── Header ── */}
      <div style={{ background: `linear-gradient(180deg, #0d1120 0%, ${C.bg} 100%)`, borderBottom: `1px solid ${C.border}`, padding: "36px 24px 0" }}>
        <div style={{ maxWidth: 980, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", color: C.blue, textTransform: "uppercase", marginBottom: 8 }}>
            Manager Portal
          </p>
          <h1 style={{ fontSize: "clamp(1.6rem,4vw,2.4rem)", fontWeight: 800, letterSpacing: "-0.02em", margin: "0 0 24px" }}>
            Manager Dashboard
          </h1>

          {/* Tab bar */}
          <div style={{ display: "flex", gap: 4 }}>
            {tabs.map(({ key, label, count }) => {
              const active = tab === key;
              return (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  style={{
                    padding: "10px 20px",
                    border: "none",
                    borderBottom: active ? `2px solid ${C.blue}` : "2px solid transparent",
                    background: "transparent",
                    color: active ? C.fg : C.muted,
                    fontSize: 14,
                    fontWeight: active ? 700 : 500,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    transition: "color 0.15s",
                    borderRadius: "8px 8px 0 0",
                  }}
                >
                  {label}
                  <span style={{
                    background: active ? `${C.blue}22` : C.raised,
                    color: active ? C.blue : C.muted,
                    border: `1px solid ${active ? C.blue + "44" : C.border}`,
                    borderRadius: 999,
                    padding: "1px 8px",
                    fontSize: 11,
                    fontWeight: 700,
                  }}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 980, margin: "0 auto", padding: "28px 24px" }}>

        {/* ════ SHOWS TAB ════ */}
        {tab === "shows" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <SectionCard>
              <SectionTitle>Create Show</SectionTitle>
              <form onSubmit={createShow} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Event">
                  <select style={inputStyle} value={newShow.event_id}
                    onChange={e => setNewShow(s => ({ ...s, event_id: e.target.value }))} required>
                    <option value="">Select event</option>
                    {events.map(ev => (
                      <option key={ev.id} value={ev.id}>
                        {ev.title}{ev.status !== "published" ? " (draft)" : ""}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Screen">
                  <select style={inputStyle} value={newShow.screen_id}
                    onChange={e => setNewShow(s => ({ ...s, screen_id: e.target.value }))} required>
                    <option value="">Select screen</option>
                    {screens.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
                  </select>
                </Field>
                <Field label="Start Time">
                  <input style={inputStyle} type="datetime-local" value={newShow.start_time}
                    onChange={e => setNewShow(s => ({ ...s, start_time: e.target.value }))} required />
                </Field>
                <Field label="End Time">
                  <input style={inputStyle} type="datetime-local" value={newShow.end_time}
                    onChange={e => setNewShow(s => ({ ...s, end_time: e.target.value }))} required />
                </Field>
                <Field label="Base Price (₹)">
                  <input style={inputStyle} type="number" value={newShow.base_price}
                    onChange={e => setNewShow(s => ({ ...s, base_price: e.target.value }))} required />
                </Field>
                <Field label="Load screens for venue">
                  <select style={inputStyle} onChange={e => loadScreens(e.target.value)}>
                    <option value="">Select venue to load screens</option>
                    {venues.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                  </select>
                </Field>
                <div style={{ gridColumn: "1 / -1" }}>
                  <button type="submit" style={{ width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                    Create Show
                  </button>
                </div>
              </form>
            </SectionCard>

            <SectionCard>
              <SectionTitle>All Shows ({shows.length})</SectionTitle>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {shows.map(s => {
                  const parentEvent = eventMap[s.event_id];
                  return (
                    <div key={s.id} style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "12px 16px",
                      background: C.raised,
                      border: `1px solid ${C.border}`,
                      borderRadius: 12,
                      gap: 12,
                      flexWrap: "wrap",
                    }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3, flexWrap: "wrap" }}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>{s.event_title}</span>
                          {parentEvent && <HiddenHint eventStatus={parentEvent.status} />}
                        </div>
                        <p style={{ fontSize: 12, color: C.muted, margin: "0 0 1px" }}>{s.venue_name} — {s.screen_name}</p>
                        <p style={{ fontSize: 12, color: C.muted, margin: 0 }}>{new Date(s.start_time).toLocaleString("en-IN")}</p>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ color: C.blue, fontWeight: 800, fontSize: 15 }}>₹{s.base_price}</span>
                        <button
                          onClick={() => deleteShow(s.id)}
                          style={{ background: `${C.red}15`, border: `1px solid ${C.red}44`, color: C.red, borderRadius: 8, padding: "5px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })}
                {shows.length === 0 && (
                  <p style={{ color: C.muted, fontSize: 13, textAlign: "center", padding: "24px 0" }}>No shows yet. Create one above.</p>
                )}
              </div>
            </SectionCard>
          </div>
        )}

        {/* ════ EVENTS TAB ════ */}
        {tab === "events" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <SectionCard>
              <SectionTitle>Create Event</SectionTitle>
              <p style={{ fontSize: 12, color: C.muted, marginBottom: 18, marginTop: -12 }}>
                Events are saved as <strong style={{ color: C.amber }}>Draft</strong> by default. Use the Publish button on each event to make its shows visible on Browse.
              </p>
              <form onSubmit={createEvent} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Title">
                  <input style={inputStyle} value={newEvent.title}
                    onChange={e => setNewEvent(v => ({ ...v, title: e.target.value }))} required />
                </Field>
                <Field label="Type">
                  <select style={inputStyle} value={newEvent.event_type}
                    onChange={e => setNewEvent(v => ({ ...v, event_type: e.target.value }))}>
                    {["movie","concert","theatre","other"].map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
                  </select>
                </Field>
                <Field label="Language">
                  <input style={inputStyle} value={newEvent.language}
                    onChange={e => setNewEvent(v => ({ ...v, language: e.target.value }))} />
                </Field>
                <Field label="Duration (min)">
                  <input style={inputStyle} type="number" value={newEvent.duration_minutes}
                    onChange={e => setNewEvent(v => ({ ...v, duration_minutes: e.target.value }))} />
                </Field>
                <div style={{ gridColumn: "1 / -1" }}>
                  <button type="submit" style={{ width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                    Create Event (Draft)
                  </button>
                </div>
              </form>
            </SectionCard>

            <SectionCard>
              <SectionTitle>Events ({events.length})</SectionTitle>
              {events.length === 0 && (
                <p style={{ color: C.muted, fontSize: 13, textAlign: "center", padding: "24px 0" }}>No events yet.</p>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {events.map(ev => (
                  <div key={ev.id} style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 14,
                    padding: "14px 18px",
                    background: C.raised,
                    border: `1px solid ${C.border}`,
                    borderRadius: 12,
                    flexWrap: "wrap",
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4, flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 700, fontSize: 15 }}>{ev.title}</span>
                        <Badge status={ev.status} />
                      </div>
                      <p style={{ fontSize: 12, color: C.muted, margin: "0 0 3px" }}>
                        {ev.event_type}{ev.language ? ` · ${ev.language}` : ""}{ev.duration_minutes ? ` · ${ev.duration_minutes} min` : ""}
                      </p>
                      {ev.status === "draft" && (
                        <p style={{ fontSize: 11, color: C.amber, margin: 0 }}>
                          ⚠ Shows for this event won't appear on Browse until published.
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => togglePublish(ev)}
                      disabled={togglingId === ev.id}
                      style={{
                        padding: "8px 20px",
                        borderRadius: 8,
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: togglingId === ev.id ? "not-allowed" : "pointer",
                        opacity: togglingId === ev.id ? 0.5 : 1,
                        transition: "all 0.15s",
                        border: ev.status === "published" ? `1.5px solid ${C.red}44` : `1.5px solid ${C.green}44`,
                        background: ev.status === "published" ? `${C.red}12` : `${C.green}12`,
                        color: ev.status === "published" ? C.red : C.green,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {togglingId === ev.id ? "…" : ev.status === "published" ? "Unpublish" : "Publish"}
                    </button>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        )}

        {/* ════ VENUES TAB ════ */}
        {tab === "venues" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <SectionCard>
              <SectionTitle>Create Venue</SectionTitle>
              <form onSubmit={createVenue} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Name">
                  <input style={inputStyle} value={newVenue.name}
                    onChange={e => setNewVenue(v => ({ ...v, name: e.target.value }))} required />
                </Field>
                <Field label="City">
                  <input style={inputStyle} value={newVenue.city}
                    onChange={e => setNewVenue(v => ({ ...v, city: e.target.value }))} required />
                </Field>
                <div style={{ gridColumn: "1 / -1" }}>
                  <Field label="Address">
                    <input style={inputStyle} value={newVenue.address}
                      onChange={e => setNewVenue(v => ({ ...v, address: e.target.value }))} />
                  </Field>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                  <button type="submit" style={{ width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                    Create Venue
                  </button>
                </div>
              </form>
            </SectionCard>

            <SectionCard>
              <SectionTitle>Venues ({venues.length})</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
                {venues.map(v => (
                  <div key={v.id} style={{
                    padding: "14px 16px",
                    background: C.raised,
                    border: `1px solid ${C.border}`,
                    borderRadius: 12,
                  }}>
                    <p style={{ fontWeight: 600, fontSize: 14, margin: "0 0 3px" }}>🏛 {v.name}</p>
                    <p style={{ fontSize: 12, color: C.muted, margin: 0 }}>📍 {v.city}</p>
                  </div>
                ))}
                {venues.length === 0 && (
                  <p style={{ color: C.muted, fontSize: 13 }}>No venues yet.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard>
              <SectionTitle>Manage Screens</SectionTitle>
              <div style={{ marginBottom: 20 }}>
                <Field label="Select Venue">
                  <select style={inputStyle} value={selectedVenueId}
                    onChange={async (e) => { setSelectedVenueId(e.target.value); await loadScreens(e.target.value); }}>
                    <option value="">Select venue</option>
                    {venues.map(v => <option key={v.id} value={v.id}>{v.name} — {v.city}</option>)}
                  </select>
                </Field>
              </div>

              {selectedVenueId && (
                <>
                  <form onSubmit={createScreen} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 24 }}>
                    <Field label="Screen Name">
                      <input style={inputStyle} value={newScreen.name}
                        onChange={e => setNewScreen(s => ({ ...s, name: e.target.value }))} required />
                    </Field>
                    <Field label="Rows">
                      <input style={inputStyle} type="number" value={newScreen.rows}
                        onChange={e => setNewScreen(s => ({ ...s, rows: e.target.value }))} required />
                    </Field>
                    <Field label="Columns">
                      <input style={inputStyle} type="number" value={newScreen.cols}
                        onChange={e => setNewScreen(s => ({ ...s, cols: e.target.value }))} required />
                    </Field>
                    <Field label="Capacity">
                      <div style={{ ...inputStyle, color: C.muted, background: C.bg }}>
                        {(parseInt(newScreen.rows)||0)*(parseInt(newScreen.cols)||0)} seats
                      </div>
                    </Field>
                    <div style={{ gridColumn: "1 / -1" }}>
                      <button type="submit" style={{ width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                        Create Screen
                      </button>
                    </div>
                  </form>

                  <h3 style={{ fontSize: 13, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
                    Screens
                  </h3>
                  {screens.length === 0 ? (
                    <p style={{ color: C.muted, fontSize: 13 }}>No screens for this venue yet.</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {screens.map(sc => (
                        <div key={sc.id} style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "12px 16px",
                          background: C.raised,
                          border: `1px solid ${C.border}`,
                          borderRadius: 10,
                        }}>
                          <div>
                            <p style={{ fontWeight: 600, fontSize: 14, margin: "0 0 2px" }}>🎞 {sc.name}</p>
                            <p style={{ fontSize: 12, color: C.muted, margin: 0 }}>{sc.capacity} seats</p>
                          </div>
                          <span style={{ fontSize: 11, fontWeight: 700, color: C.green, background: `${C.green}15`, border: `1px solid ${C.green}44`, borderRadius: 999, padding: "3px 10px" }}>
                            Active
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </SectionCard>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        input:focus, select:focus { border-color: ${C.blue} !important; box-shadow: 0 0 0 3px ${C.blue}22; }
        @media (max-width: 600px) {
          form[style*="grid-template-columns"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
