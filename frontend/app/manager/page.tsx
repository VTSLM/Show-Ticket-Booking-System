"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { managerApi, organizerVerificationApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { reviewsApi, ReportedReview } from "@/lib/reviewsApi";
import { LAYOUT_LABELS, layoutFits, layoutWarning } from "@/lib/layouts";

type Tab = "shows" | "events" | "venues" | "reports" | "coupons";

const REASON_LABEL: Record<string, string> = {
  spam: "Spam or advertising",
  abusive: "Abusive or offensive",
  spoiler: "Spoiler not marked",
  off_topic: "Not about this event",
  other: "Something else",
};

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
  const { user, isManager, loading: authLoading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("shows");
  const [shows, setShows] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [venues, setVenues] = useState<any[]>([]);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [newCoupon, setNewCoupon] = useState({ code: "", percent_off: "20" });
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Reported reviews
  const [reports, setReports] = useState<ReportedReview[]>([]);
  const [reportFilter, setReportFilter] = useState<"open" | "all">("open");
  const [reportsLoading, setReportsLoading] = useState(false);

  const [newEvent, setNewEvent] = useState({ title: "", event_type: "movie", language: "", duration_minutes: "", organizer_id: "", description: "", terms_and_conditions: "" });
  const [newVenue, setNewVenue] = useState({ name: "", city: "", address: "" });
  const [newShow, setNewShow] = useState({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "", premium_multiplier: "1.5", terms_and_conditions: "", dynamic_pricing: false });
  const [showZones, setShowZones] = useState<{ name: string; total_capacity: number; price: number; zone_type: string; color_hex: string }[]>([]);
  const [screens, setScreens] = useState<any[]>([]);
  const [selectedVenueId, setSelectedVenueId] = useState("");
  const [newScreen, setNewScreen] = useState({ name: "", rows: "", cols: "", layout_type: "cinema", stage_position: "front", premium_rows: "" });

  useEffect(() => {
    if (!authLoading && !isManager) { router.push("/"); return; }
    if (!authLoading && isManager) {
      Promise.allSettled([
        managerApi.shows().then(setShows),
        managerApi.events().then(setEvents),
        managerApi.venues().then(setVenues),
        managerApi.coupons().then(setCoupons),
        organizerVerificationApi.myApplications().then(apps => {
          setOrganizations(apps || []);
          const approved = (apps || []).filter((a: any) => a.verification_status === "APPROVED");
          if (approved.length > 0) {
            setNewEvent(v => ({ ...v, organizer_id: approved[0].id }));
          }
        }),
      ]).then((results) => {
        results.forEach((r) => {
          if (r.status === "rejected") {
            console.error("Dashboard init error:", r.reason);
          }
        });
      }).finally(() => setLoading(false));
    }
  }, [isManager, authLoading]);

  const approvedOrgs = organizations.filter(o => o.verification_status === "APPROVED");
  const selectedVenue = venues.find(v => v.id === selectedVenueId);

  const eventMap = Object.fromEntries(events.map(ev => [ev.id, ev]));
  // Screens whose layout suits the chosen event come first; a mismatch shows a warning (#168)
  const selectedEvent = newShow.event_id ? eventMap[newShow.event_id] : null;
  const sortedScreens = [...screens].sort(
    (a, b) => Number(layoutFits(selectedEvent?.event_type, b.layout_type)) - Number(layoutFits(selectedEvent?.event_type, a.layout_type))
  );
  const selectedScreen = screens.find(sc => sc.id === newShow.screen_id);
  const screenWarning = selectedEvent && selectedScreen ? layoutWarning(selectedEvent.event_type, selectedScreen.layout_type) : null;

  const loadReports = async (filter: "open" | "all" = reportFilter) => {
    if (!user) return;
    setReportsLoading(true);
    try {
      const token = await user.getIdToken();
      const res = await reviewsApi.reports(token, filter);
      setReports(res.items);
    } catch (err: any) {
      toast.error(err.message || "Could not load reports");
    } finally {
      setReportsLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "reports" && !authLoading && isManager) loadReports(reportFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, reportFilter, authLoading, isManager]);

  const resolveReports = async (reviewId: string, status: "dismissed" | "reviewed") => {
    try {
      const token = await user.getIdToken();
      await reviewsApi.resolveReports(token, reviewId, status);
      toast.success(status === "dismissed" ? "Reports dismissed" : "Marked as reviewed");
      await loadReports(reportFilter);
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const removeReview = async (r: ReportedReview) => {
    if (!user) return;
    if (!confirm(`Remove "${r.headline}" by ${r.author_name}? This deletes the review and its comments permanently.`)) return;
    try {
      const token = await user.getIdToken();
      await reviewsApi.remove(token, r.review_id);
      toast.success("Review removed");
      await loadReports(reportFilter);
    } catch (err: any) {
      toast.error(err.message || "Could not remove review");
    }
  };

  const createCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await managerApi.createCoupon({
        code: newCoupon.code.trim().toUpperCase(),
        percent_off: Number(newCoupon.percent_off),
      });
      setNewCoupon({ code: "", percent_off: "20" });
      setCoupons(await managerApi.coupons());
      toast.success("Coupon created");
    } catch (err: any) {
      toast.error(err.message || "Could not create coupon");
    }
  };

  const changeCouponStatus = async (code: string, isActive: boolean) => {
    try {
      await managerApi.setCouponActive(code, isActive);
      setCoupons(await managerApi.coupons());
      toast.success(isActive ? "Coupon activated" : "Coupon deactivated");
    } catch (err: any) {
      toast.error(err.message || "Could not update coupon");
    }
  };

  const loadScreens = async (venueId: string) => {
    if (!venueId) { setScreens([]); return; }
    try { setScreens(await managerApi.screens(venueId)); }
    catch (err: any) { toast.error(err.message || "Could not load screens"); setScreens([]); }
  };

  const createEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (approvedOrgs.length === 0) {
      toast.error("Organizer verification required: Please complete organizer verification before creating events.");
      return;
    }
    try {
      await managerApi.createEvent({
        ...newEvent,
        duration_minutes: parseInt(newEvent.duration_minutes) || undefined,
        organizer_id: newEvent.organizer_id || approvedOrgs[0]?.id,
      });
      setEvents(await managerApi.events());
      setNewEvent({
        title: "",
        event_type: "movie",
        language: "",
        duration_minutes: "",
        organizer_id: approvedOrgs[0]?.id || "",
        description: "",
        terms_and_conditions: "",
      });
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
    const premRows = newScreen.premium_rows
      .split(",")
      .map(s => s.trim().toUpperCase())
      .filter(Boolean);
    try {
      await managerApi.createScreen(selectedVenueId, {
        name: newScreen.name,
        capacity: rows * cols,
        rows,
        cols,
        layout_type: newScreen.layout_type,
        stage_position: newScreen.stage_position,
        premium_rows: premRows,
      });
      setScreens(await managerApi.screens(selectedVenueId));
      setNewScreen({ name: "", rows: "", cols: "", layout_type: "cinema", stage_position: "front", premium_rows: "" });
      toast.success(`Screen created with ${rows * cols} seats (${newScreen.layout_type.toUpperCase()} layout)!`);
    } catch (err: any) { toast.error(err.message || "Could not create screen"); }
  };

  const createShow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedScreen && (selectedScreen.capacity === 0 || selectedScreen.seat_count === 0) && showZones.length === 0) {
      toast.error("Cannot create show: the selected screen has no seats configured and no admission zones were provided.");
      return;
    }
    try {
      await managerApi.createShow({
        ...newShow,
        base_price: parseFloat(newShow.base_price),
        premium_multiplier: parseFloat(newShow.premium_multiplier) || 1.5,
        zones: showZones.length > 0 ? showZones : undefined,
      });
      setShows(await managerApi.shows());
      setNewShow({ event_id: "", screen_id: "", start_time: "", end_time: "", base_price: "", premium_multiplier: "1.5", terms_and_conditions: "", dynamic_pricing: false });
      setShowZones([]);
      toast.success("Show created with custom layout and pricing!");
    } catch (err: any) { toast.error(err.message); }
  };

  const toggleDynamicPricing = async (id: string, enabled: boolean) => {
    try {
      await managerApi.setDynamicPricing(id, enabled);
      setShows(ss => ss.map(s => (s.id === id ? { ...s, dynamic_pricing: enabled } : s)));
      toast.success(enabled ? "Dynamic pricing turned on" : "Dynamic pricing turned off");
    } catch (err: any) { toast.error(err.message || "Could not update pricing"); }
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

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "shows", label: "Shows", count: shows.length },
    { key: "events", label: "Events", count: events.length },
    { key: "venues", label: "Venues", count: venues.length },
    { key: "reports", label: "Reported reviews" },
    { key: "coupons", label: "Coupons", count: coupons.length },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.fg }}>
      {/* ── Header ── */}
      <div style={{ background: `linear-gradient(180deg, #0d1120 0%, ${C.bg} 100%)`, borderBottom: `1px solid ${C.border}`, padding: "36px 24px 0" }}>
        <div style={{ maxWidth: 980, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", color: C.blue, textTransform: "uppercase", marginBottom: 8 }}>
            Manager Portal
          </p>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", margin: "0 0 24px" }}>
            <h1 style={{ fontSize: "clamp(1.6rem,4vw,2.4rem)", fontWeight: 800, letterSpacing: "-0.02em", margin: 0 }}>
              Manager Dashboard
            </h1>
            <Link href="/manager/analytics" className="btn-primary" style={{ fontSize: 14 }}>
              📊 Analytics
            </Link>
          </div>

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
                  {count !== undefined && <span style={{
                    background: active ? `${C.blue}22` : C.raised,
                    color: active ? C.blue : C.muted,
                    border: `1px solid ${active ? C.blue + "44" : C.border}`,
                    borderRadius: 999,
                    padding: "1px 8px",
                    fontSize: 11,
                    fontWeight: 700,
                  }}>
                    {count}
                  </span>}
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
                    {sortedScreens.map(sc => (
                      <option key={sc.id} value={sc.id}>
                        {sc.name} · {LAYOUT_LABELS[sc.layout_type] ?? sc.layout_type ?? "Cinema"}
                        {selectedEvent && !layoutFits(selectedEvent.event_type, sc.layout_type) ? " (different layout)" : ""}
                      </option>
                    ))}
                  </select>
                  {screenWarning && (
                    <p role="alert" style={{ marginTop: 6, fontSize: 12, color: "#fbbf24" }}>⚠ {screenWarning}</p>
                  )}
                  {selectedScreen && (selectedScreen.capacity === 0 || selectedScreen.seat_count === 0) && showZones.length === 0 && (
                    <p role="alert" style={{ marginTop: 6, fontSize: 12, color: "#f87171" }}>
                      ⚠ Selected screen has 0 seats. Add standing / festival zones below or select a screen with seats to schedule a show.
                    </p>
                  )}
                </Field>
                <Field label="Start Time">
                  <input style={inputStyle} type="datetime-local" value={newShow.start_time}
                    onChange={e => setNewShow(s => ({ ...s, start_time: e.target.value }))} required />
                </Field>
                <Field label="End Time">
                  <input style={inputStyle} type="datetime-local" value={newShow.end_time}
                    onChange={e => setNewShow(s => ({ ...s, end_time: e.target.value }))} required />
                </Field>
                <Field label="Base Price for Standard Seats (₹)">
                  <input style={inputStyle} type="number" value={newShow.base_price}
                    onChange={e => setNewShow(s => ({ ...s, base_price: e.target.value }))} required />
                </Field>
                <Field label="Premium Seat Multiplier">
                  <input style={inputStyle} type="number" step="0.1" value={newShow.premium_multiplier}
                    onChange={e => setNewShow(s => ({ ...s, premium_multiplier: e.target.value }))} placeholder="1.5" />
                </Field>
                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer", padding: "12px 14px", background: C.raised, border: `1px solid ${newShow.dynamic_pricing ? C.blue : C.border}`, borderRadius: 10 }}>
                    <input type="checkbox" checked={newShow.dynamic_pricing}
                      onChange={e => setNewShow(s => ({ ...s, dynamic_pricing: e.target.checked }))}
                      style={{ marginTop: 3, accentColor: C.blue }} />
                    <span>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>⚡ Enable dynamic pricing</span>
                      <span style={{ display: "block", fontSize: 12, color: C.muted, marginTop: 2 }}>
                        Prices adjust automatically: +10% when 50% sold, +25% when 80% sold, +15% in the last 24 hours,
                        +10% for Fri–Sun evening shows. Movies: −10% off-peak (Mon–Fri before 5 PM).
                        Concerts &amp; theatre: −10% early-bird (7+ days before). Always between 0.8× and 1.5× the base price.
                      </span>
                    </span>
                  </label>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                  <Field label="Filter Screens by Venue">
                    <select style={inputStyle} value={selectedVenueId}
                      onChange={async (e) => { setSelectedVenueId(e.target.value); await loadScreens(e.target.value); }}>
                      <option value="">Select venue to load screens</option>
                      {venues.map(v => (
                        <option key={v.id} value={v.id}>
                          {v.name} — {v.city} {v.verification_status === "approved" ? "✓" : "(Pending Verification)"}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>

                {/* ── Standing Zones Section ── */}
                <div style={{ gridColumn: "1 / -1", padding: "16px", background: C.raised, borderRadius: 12, border: `1px solid ${C.border}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
                    <div>
                      <h4 style={{ fontSize: 13, fontWeight: 700, margin: 0, color: C.fg }}>🎸 Concert & Festival Zones (Standing / Fan Pit)</h4>
                      <p style={{ fontSize: 11, color: C.muted, margin: "2px 0 0" }}>Define unreserved standing sections with capacity limits for this show</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowZones(z => [...z, { name: "VIP Fan Pit", total_capacity: 250, price: (parseFloat(newShow.base_price) || 500) * 2, zone_type: "standing", color_hex: "#ff0055" }])}
                      style={{ background: `${C.blue}20`, border: `1px solid ${C.blue}66`, color: C.blue, padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer" }}
                    >
                      + Add Standing Zone
                    </button>
                  </div>

                  {showZones.length === 0 ? (
                    <p style={{ fontSize: 12, color: C.muted, margin: 0, fontStyle: "italic" }}>No standing zones added yet. Numbered seats from the screen will be used.</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {showZones.map((zone, idx) => (
                        <div key={idx} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 10, alignItems: "center", background: C.surface, padding: "10px", borderRadius: 8, border: `1px solid ${C.border}` }}>
                          <div>
                            <input
                              style={{ ...inputStyle, padding: "6px 10px", fontSize: 12 }}
                              value={zone.name}
                              placeholder="Zone name (e.g. Fan Pit)"
                              onChange={e => {
                                const val = e.target.value;
                                setShowZones(zs => zs.map((item, i) => i === idx ? { ...item, name: val } : item));
                              }}
                            />
                          </div>
                          <div>
                            <input
                              style={{ ...inputStyle, padding: "6px 10px", fontSize: 12 }}
                              type="number"
                              value={zone.total_capacity}
                              placeholder="Capacity"
                              onChange={e => {
                                const val = parseInt(e.target.value) || 0;
                                setShowZones(zs => zs.map((item, i) => i === idx ? { ...item, total_capacity: val } : item));
                              }}
                            />
                          </div>
                          <div>
                            <input
                              style={{ ...inputStyle, padding: "6px 10px", fontSize: 12 }}
                              type="number"
                              value={zone.price}
                              placeholder="Price (₹)"
                              onChange={e => {
                                const val = parseFloat(e.target.value) || 0;
                                setShowZones(zs => zs.map((item, i) => i === idx ? { ...item, price: val } : item));
                              }}
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => setShowZones(zs => zs.filter((_, i) => i !== idx))}
                            style={{ background: `${C.red}20`, border: `1px solid ${C.red}66`, color: C.red, borderRadius: 6, padding: "6px 10px", cursor: "pointer", fontSize: 12 }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
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
                          onClick={() => toggleDynamicPricing(s.id, !s.dynamic_pricing)}
                          title={s.dynamic_pricing ? "Dynamic pricing is ON — click to use fixed prices" : "Fixed prices — click to turn on dynamic pricing"}
                          style={{ background: s.dynamic_pricing ? `${C.blue}22` : C.surface, border: `1px solid ${s.dynamic_pricing ? C.blue : C.border}`, color: s.dynamic_pricing ? C.blue : C.muted, borderRadius: 8, padding: "5px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          ⚡ Dynamic {s.dynamic_pricing ? "ON" : "OFF"}
                        </button>
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
            {approvedOrgs.length === 0 && (
              <div style={{
                padding: "20px 24px",
                borderRadius: 14,
                background: `${C.amber}15`,
                border: `1.5px solid ${C.amber}44`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 16
              }}>
                <div>
                  <h3 style={{ margin: "0 0 6px", fontSize: 16, fontWeight: 700, color: C.amber }}>
                    🛡️ Organizer Verification Required
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: C.muted, maxWidth: 600 }}>
                    In compliance with ticketing regulations, events can only be created by an approved organization. Submit your PAN, GSTIN, and Bank Proof to get verified.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => router.push("/verification/organizer")}
                  style={{
                    background: C.amber,
                    color: "#000",
                    border: "none",
                    borderRadius: 10,
                    padding: "10px 20px",
                    fontSize: 13,
                    fontWeight: 800,
                    cursor: "pointer",
                    whiteSpace: "nowrap"
                  }}
                >
                  Verify Organization →
                </button>
              </div>
            )}

            <SectionCard>
              <SectionTitle>Create Event</SectionTitle>
              <p style={{ fontSize: 12, color: C.muted, marginBottom: 18, marginTop: -12 }}>
                Events are saved as <strong style={{ color: C.amber }}>Draft</strong> by default. Use the Publish button on each event to make its shows visible on Browse.
              </p>
              <form onSubmit={createEvent} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div style={{ gridColumn: "1 / -1" }}>
                  <Field label="Host Organization">
                    <select
                      style={inputStyle}
                      value={newEvent.organizer_id}
                      onChange={e => setNewEvent(v => ({ ...v, organizer_id: e.target.value }))}
                      required
                    >
                      {approvedOrgs.length === 0 && <option value="">No approved organization (Verification required)</option>}
                      {approvedOrgs.map(org => (
                        <option key={org.id} value={org.id}>
                          🏢 {org.legal_name} ({org.business_type} · Verified)
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
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
                      {ev.organization_name && (
                        <p style={{ fontSize: 12, color: C.blue, margin: "0 0 4px", fontWeight: 600 }}>
                          🏢 Host: {ev.organization_name}
                        </p>
                      )}
                      <p style={{ fontSize: 12, color: C.muted, margin: "0 0 3px" }}>
                        {ev.event_type}{ev.language ? ` · ${ev.language}` : ""}{ev.duration_minutes ? ` · ${ev.duration_minutes} min` : ""}
                      </p>
                      {ev.status === "draft" && (
                        <p style={{ fontSize: 11, color: C.amber, margin: 0 }}>
                          ⚠ Shows for this event won&apos;t appear on Browse until published.
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
                <SectionTitle>Create Venue</SectionTitle>
                <button
                  type="button"
                  onClick={() => router.push("/verification/venue")}
                  style={{
                    background: "transparent",
                    color: C.blue,
                    border: `1px solid ${C.blue}55`,
                    borderRadius: 8,
                    padding: "6px 14px",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Submit Venue Safety Documents →
                </button>
              </div>
              <p style={{ fontSize: 12, color: C.muted, margin: "-10px 0 16px" }}>
                New venues are submitted for compliance & safety verification. Once verified by admin, you can schedule public shows.
              </p>
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
                    Create Venue & Register Case
                  </button>
                </div>
              </form>
            </SectionCard>

            <SectionCard>
              <SectionTitle>Venues ({venues.length})</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
                {venues.map(v => {
                  const isApproved = v.verification_status === "approved";
                  return (
                    <div key={v.id} style={{
                      padding: "16px",
                      background: C.raised,
                      border: `1px solid ${isApproved ? C.border : C.amber + "33"}`,
                      borderRadius: 12,
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                        <p style={{ fontWeight: 700, fontSize: 14, margin: 0 }}>🏛 {v.name}</p>
                        <span style={{
                          fontSize: 9,
                          fontWeight: 800,
                          padding: "2px 8px",
                          borderRadius: 999,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          background: isApproved ? `${C.green}18` : `${C.amber}18`,
                          color: isApproved ? C.green : C.amber,
                          border: `1px solid ${isApproved ? C.green + "44" : C.amber + "44"}`,
                        }}>
                          {isApproved ? "✓ Verified" : "⚠ Pending Safety Review"}
                        </span>
                      </div>
                      <p style={{ fontSize: 12, color: C.muted, margin: 0 }}>📍 {v.city}</p>
                    </div>
                  );
                })}
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
                    {venues.map(v => (
                      <option key={v.id} value={v.id}>
                        {v.name} — {v.city} {v.verification_status === "approved" ? "✓" : "(Pending Verification)"}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              {selectedVenue && selectedVenue.verification_status !== "approved" && (
                <div style={{ padding: "12px 16px", borderRadius: 10, background: `${C.amber}14`, border: `1px solid ${C.amber}44`, marginBottom: 18 }}>
                  <p style={{ margin: 0, fontSize: 12, color: C.amber, fontWeight: 600 }}>
                    ⚠ Venue &quot;{selectedVenue.name}&quot; is pending safety compliance verification. Layouts can be configured, but public shows cannot be scheduled until admin approves venue safety documents.
                  </p>
                </div>
              )}

              {selectedVenueId && (
                <>
                  <form onSubmit={createScreen} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 24 }}>
                    <Field label="Screen / Stage Name">
                      <input style={inputStyle} value={newScreen.name}
                        onChange={e => setNewScreen(s => ({ ...s, name: e.target.value }))} required />
                    </Field>
                    <Field label="Layout Template">
                      <select style={inputStyle} value={newScreen.layout_type}
                        onChange={e => setNewScreen(s => ({ ...s, layout_type: e.target.value }))}>
                        <option value="cinema">🎬 Cinema Proscenium (Screen + Rows)</option>
                        <option value="concert">🎸 Concert Arena / Stadium (Stage + Fan Pit + Stands)</option>
                        <option value="theatre">🎭 Auditorium / Theatre (Stage + Stalls + Balcony)</option>
                        <option value="other">🎟️ General Admission / Passes (Open Lawn / Table)</option>
                      </select>
                    </Field>
                    <Field label="Rows">
                      <input style={inputStyle} type="number" value={newScreen.rows}
                        onChange={e => setNewScreen(s => ({ ...s, rows: e.target.value }))} required />
                    </Field>
                    <Field label="Columns">
                      <input style={inputStyle} type="number" value={newScreen.cols}
                        onChange={e => setNewScreen(s => ({ ...s, cols: e.target.value }))} required />
                    </Field>
                    <Field label="Mark Premium Rows (e.g. A, B)">
                      <input style={inputStyle} placeholder="e.g. A, B or D, E" value={newScreen.premium_rows}
                        onChange={e => setNewScreen(s => ({ ...s, premium_rows: e.target.value }))} />
                    </Field>
                    <Field label="Stage Position">
                      <select style={inputStyle} value={newScreen.stage_position}
                        onChange={e => setNewScreen(s => ({ ...s, stage_position: e.target.value }))}>
                        <option value="front">Front Stage</option>
                        <option value="center">Center Stage (360° In-the-Round)</option>
                        <option value="end">End Stage</option>
                      </select>
                    </Field>
                    <div style={{ gridColumn: "1 / -1" }}>
                      <button type="submit" style={{ width: "100%", background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
                        Create Screen / Stage Layout
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

        {/* ════ COUPONS TAB ════ */}
        {tab === "coupons" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <SectionCard>
              <SectionTitle>Create Coupon</SectionTitle>
              <form
                onSubmit={createCoupon}
                style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 14, alignItems: "end" }}
              >
                <Field label="Coupon code">
                  <input
                    style={inputStyle}
                    value={newCoupon.code}
                    onChange={e => setNewCoupon(current => ({ ...current, code: e.target.value }))}
                    minLength={3}
                    maxLength={40}
                    pattern="[A-Za-z0-9_-]{3,40}"
                    required
                  />
                </Field>
                <Field label="Discount percentage">
                  <input
                    style={inputStyle}
                    type="number"
                    min="0.01"
                    max="99.99"
                    step="0.01"
                    value={newCoupon.percent_off}
                    onChange={e => setNewCoupon(current => ({ ...current, percent_off: e.target.value }))}
                    required
                  />
                </Field>
                <button type="submit" className="btn-primary">
                  Create coupon
                </button>
              </form>
            </SectionCard>

            <SectionCard>
              <SectionTitle>Coupons ({coupons.length})</SectionTitle>
              <div style={{ display: "grid", gap: 12 }}>
                {coupons.map(coupon => (
                  <div
                    key={coupon.id}
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}
                  >
                    <span>
                      <strong>{coupon.code}</strong> — {Number(coupon.percent_off)}% off —{" "}
                      {coupon.is_active ? "Active" : "Inactive"}
                    </span>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => changeCouponStatus(coupon.code, !coupon.is_active)}
                    >
                      {coupon.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                ))}
                {coupons.length === 0 && (
                  <p style={{ color: C.muted, fontSize: 13, textAlign: "center" }}>
                    No coupons yet.
                  </p>
                )}
              </div>
            </SectionCard>
          </div>
        )}

        {/* ════ REPORTED REVIEWS TAB ════ */}
        {tab === "reports" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, color: C.fg, margin: 0 }}>Reported reviews</h2>
              <select
                style={{ ...inputStyle, width: "auto" }}
                value={reportFilter}
                onChange={e => setReportFilter(e.target.value as "open" | "all")}
              >
                <option value="open">Open only</option>
                <option value="all">All (including closed)</option>
              </select>
            </div>

            {reportsLoading ? (
              <SectionCard><p style={{ color: C.muted, fontSize: 13, textAlign: "center", margin: 0 }}>Loading…</p></SectionCard>
            ) : reports.length === 0 ? (
              <SectionCard><p style={{ color: C.muted, fontSize: 13, textAlign: "center", margin: 0 }}>No reported reviews.</p></SectionCard>
            ) : reports.map(r => (
              <SectionCard key={r.review_id} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: 12, color: C.muted, margin: "0 0 4px" }}>
                      {r.event_title} · by {r.author_name} · {r.rating.toFixed(1)} / 10{!r.is_public && " · not public"}
                    </p>
                    <p style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>{r.headline}</p>
                  </div>
                  <span style={{
                    flexShrink: 0,
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 700,
                    background: r.open_count > 0 ? `${C.red}18` : C.raised,
                    color: r.open_count > 0 ? C.red : C.muted,
                    border: `1px solid ${r.open_count > 0 ? C.red + "44" : C.border}`,
                  }}>
                    {r.open_count > 0 ? `${r.open_count} open` : "Closed"}
                  </span>
                </div>

                <p style={{ fontSize: 13, color: C.muted, margin: 0, whiteSpace: "pre-line" }}>
                  {r.content.length > 300 ? `${r.content.slice(0, 300).trimEnd()}…` : r.content}
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {r.reports.map(rp => (
                    <div key={rp.id} style={{ background: C.raised, border: `1px solid ${C.border}`, borderRadius: 10, padding: "10px 14px" }}>
                      <p style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>
                        {REASON_LABEL[rp.reason] || rp.reason}
                        <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 400, color: C.muted }}>
                          by {rp.reporter_name} · {new Date(rp.created_at).toLocaleString("en-IN")}
                          {rp.status !== "open" && ` · ${rp.status}`}
                        </span>
                      </p>
                      {rp.details && <p style={{ fontSize: 12, color: C.muted, margin: "4px 0 0" }}>{rp.details}</p>}
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <a href={`/events/${r.event_id}/reviews`} target="_blank" rel="noreferrer"
                    style={{ fontSize: 13, color: C.blue, textDecoration: "none", fontWeight: 600 }}>
                    Open reviews page →
                  </a>
                  <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button onClick={() => removeReview(r)}
                      style={{ background: `${C.red}15`, border: `1px solid ${C.red}55`, color: C.red, borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                      🗑 Remove review
                    </button>
                    {r.open_count > 0 && (<>
                      <button onClick={() => resolveReports(r.review_id, "dismissed")}
                        style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.fg, borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Dismiss
                      </button>
                      <button onClick={() => resolveReports(r.review_id, "reviewed")}
                        style={{ background: C.blue, border: "none", color: "#fff", borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                        Mark as reviewed
                      </button>
                    </>)}
                  </div>
                </div>
              </SectionCard>
            ))}
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