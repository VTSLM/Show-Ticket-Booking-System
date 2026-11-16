"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useAuth } from "@/contexts/AuthContext";
import { analyticsApi, EventAnalytics, ManagerAnalytics } from "@/lib/analyticsApi";

const C = {
  blue: "#287cff", green: "#00c977", amber: "#ffb300", red: "#ff4455", violet: "#8b5cf6",
  muted: "#9ba3b5", grid: "#292e3d", surface: "#11141e", raised: "#181c28",
};
const RANGES = [
  { days: 7, label: "7 days" }, { days: 30, label: "30 days" },
  { days: 90, label: "90 days" }, { days: 365, label: "1 year" },
];
const OUTCOME_STYLE: Record<string, { label: string; color: string }> = {
  confirmed: { label: "Confirmed", color: C.green },
  pending: { label: "Pending payment", color: C.amber },
  expired: { label: "Abandoned (expired)", color: C.muted },
  cancelled: { label: "Cancelled", color: C.red },
};

const inr = (n: number, compact = false) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: compact ? 1 : 0,
    notation: compact ? "compact" : "standard",
  }).format(n || 0);
const num = (n: number) => new Intl.NumberFormat("en-IN").format(n || 0);
const shortDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

const tooltipStyle = {
  contentStyle: { background: C.raised, border: `1px solid ${C.grid}`, borderRadius: 10, color: "#f4f6fb", fontSize: 12 },
  labelStyle: { color: C.muted },
  itemStyle: { color: "#f4f6fb" },
  cursor: { fill: "rgba(255,255,255,0.04)" },
};

function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-slate-800/80 bg-gradient-to-b from-slate-900/80 to-slate-950/80 p-5 shadow-lg shadow-black/20 ${className}`}>
      {title && <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 mb-4">{title}</h2>}
      {children}
    </section>
  );
}

function Stat({ label, value, sub, change, icon }: {
  label: string; value: string; sub?: string; change?: number | null; icon: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-gradient-to-br from-slate-900 to-slate-950 p-4 transition-colors hover:border-blue-500/40">
      <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400 flex items-center gap-1.5"><span aria-hidden="true">{icon}</span>{label}</p>
      <p className="text-2xl font-bold text-white mt-1 tracking-tight">{value}</p>
      <div className="flex items-center gap-2 mt-1 min-h-[18px]">
        {change !== undefined && change !== null && (
          <span className={`text-xs font-semibold ${change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {change >= 0 ? "▲" : "▼"} {Math.abs(change)}%
          </span>
        )}
        {sub && <span className="text-xs text-slate-500">{sub}</span>}
      </div>
    </div>
  );
}

function InsightsSlider({ items }: { items: { level: "good" | "warn" | "info"; text: string }[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = items.length;
  useEffect(() => { setI(0); }, [n]);
  useEffect(() => {
    if (n < 2 || paused) return;
    const t = setInterval(() => setI(x => (x + 1) % n), 5000);
    return () => clearInterval(t);
  }, [n, paused]);
  if (!n) return <p className="text-sm text-slate-500">Nothing unusual in this period — all looks steady. ✅</p>;
  const a = items[Math.min(i, n - 1)];
  const tone = a.level === "warn" ? { dot: "bg-amber-400", label: "Needs attention", text: "text-amber-300" }
    : a.level === "good" ? { dot: "bg-emerald-400", label: "Going well", text: "text-emerald-300" }
    : { dot: "bg-blue-400", label: "Good to know", text: "text-blue-300" };
  return (
    <div onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} aria-roledescription="carousel">
      <div className="flex items-center gap-3">
        <button type="button" aria-label="Previous insight" onClick={() => setI((i - 1 + n) % n)}
          className="h-8 w-8 shrink-0 rounded-full border border-slate-700 text-slate-300 hover:border-blue-500 hover:text-white">‹</button>
        <div className="flex-1 min-h-[52px]" aria-live="polite">
          <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${tone.text} flex items-center gap-2`}>
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />{tone.label}
            <span className="text-slate-500 normal-case tracking-normal font-normal">· {Math.min(i, n - 1) + 1} of {n}</span>
          </p>
          <p key={i} className="text-sm text-slate-100 mt-1 animate-[fadeIn_.4s_ease]">{a.text}</p>
        </div>
        <button type="button" aria-label="Next insight" onClick={() => setI((i + 1) % n)}
          className="h-8 w-8 shrink-0 rounded-full border border-slate-700 text-slate-300 hover:border-blue-500 hover:text-white">›</button>
      </div>
      <div className="flex justify-center gap-1.5 mt-3">
        {items.map((_, k) => (
          <button key={k} type="button" aria-label={`Show insight ${k + 1}`} onClick={() => setI(k)}
            className={`h-1.5 rounded-full transition-all ${k === i ? "w-5 bg-blue-500" : "w-1.5 bg-slate-700 hover:bg-slate-500"}`} />
        ))}
      </div>
      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}`}</style>
    </div>
  );
}

function PricingBadge({ dynamic }: { dynamic: boolean }) {
  return dynamic
    ? <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 whitespace-nowrap">⚡ Dynamic</span>
    : <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-300 whitespace-nowrap">Fixed</span>;
}

function Empty({ text = "No data for this period yet." }: { text?: string }) {
  return <p className="text-sm text-slate-500 py-10 text-center">{text}</p>;
}

function EventDetail({ d, onBack }: { d: EventAnalytics; onBack: () => void }) {
  const e = d.event;
  const chartShows = d.shows.map(s => ({
    ...s,
    label: new Date(s.start_time).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
  }));
  const maxCount = Math.max(1, ...d.ratings.distribution.map(r => r.count));
  return (
    <section className="card p-5 mb-6 border-blue-500/30" aria-label={`${e.title} analytics`}>
      <div className="flex flex-wrap items-start gap-4 mb-5">
        {e.poster_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={e.poster_url} alt="" className="h-24 w-16 rounded-lg object-cover border border-slate-700" />
        ) : (
          <div className="h-24 w-16 rounded-lg bg-slate-800 flex items-center justify-center text-2xl" aria-hidden="true">
            {e.event_type === "movie" ? "🎬" : e.event_type === "concert" ? "🎤" : e.event_type === "theatre" ? "🎭" : "🎟️"}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-400">Event analytics</p>
          <h2 className="text-2xl font-bold text-white truncate">{e.title}</h2>
          <p className="text-sm text-slate-400 capitalize">
            {[e.event_type, e.language, e.genre, e.duration_minutes ? `${e.duration_minutes} min` : null].filter(Boolean).join(" · ")}
            {e.status !== "published" && <span className="ml-2 text-amber-300 normal-case">({e.status})</span>}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            ⭐ {d.ratings.average === null ? "No ratings yet" : `${d.ratings.average}/10 from ${num(d.ratings.count)} reviews`}
            <span className="mx-2">·</span>❤️ {num(d.wishlisted)} wishlisted
          </p>
          <p className="text-sm text-slate-400 mt-1">
            💰 Gross {inr(d.totals.gross_revenue)} − refunds {inr(d.totals.refunds)} ={" "}
            <span className="text-white font-semibold">{inr(d.totals.revenue)} net</span>
            <span className="mx-2">·</span>🎟️ {num(d.totals.tickets)} tickets
            <span className="mx-2">·</span>⚡ {d.totals.dynamic_shows} dynamic / {d.totals.fixed_shows} fixed shows
          </p>
        </div>
        <button onClick={onBack} className="btn-secondary text-sm">← All events</button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Occupancy per show</h3>
          {chartShows.length ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartShows}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" stroke={C.muted} fontSize={11} />
                  <YAxis stroke={C.muted} fontSize={11} width={40} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                  <Tooltip {...tooltipStyle}
                    labelFormatter={(_, p: any) => (p?.[0]?.payload ? `${dateTime(p[0].payload.start_time)} · ${p[0].payload.venue}` : "")}
                    formatter={(v: any) => `${v}%`} />
                  <Bar dataKey="occupancy" name="Occupancy" radius={[4, 4, 0, 0]} maxBarSize={32}>
                    {chartShows.map(s => (
                      <Cell key={s.show_id}
                        fill={s.show_id === d.best_show_id ? C.green : s.upcoming ? C.violet : C.blue} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty text="No shows of this event in this period." />}
          <p className="text-xs text-slate-500 mt-1">
            <span className="text-emerald-400">■</span> best show · <span className="text-blue-400">■</span> past · <span className="text-violet-400">■</span> upcoming (sold so far)
          </p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Rating breakdown</h3>
          {d.ratings.count ? (
            <ul className="space-y-1">
              {d.ratings.distribution.map(r => (
                <li key={r.score} className="flex items-center gap-2 text-xs">
                  <span className="w-8 text-right text-slate-400">{r.score}/10</span>
                  <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden">
                    <div className="h-full rounded-full bg-amber-400" style={{ width: `${(r.count / maxCount) * 100}%` }} />
                  </div>
                  <span className="w-6 text-slate-500">{r.count}</span>
                </li>
              ))}
            </ul>
          ) : <Empty text="No reviews yet." />}
        </div>
      </div>

      <h3 className="text-sm font-semibold text-slate-300 mt-6 mb-3">Every show</h3>
      {d.shows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[1080px]">
            <thead>
              <tr className="text-slate-500 text-xs text-left">
                <th className="pb-2 font-medium">When</th><th className="pb-2 font-medium">Venue</th>
                <th className="pb-2 font-medium">Pricing</th>
                <th className="pb-2 font-medium text-right">Base price</th>
                <th className="pb-2 font-medium text-right" title="Average price customers actually paid per ticket">Avg paid</th>
                <th className="pb-2 font-medium w-36 pl-3">Seats sold</th><th className="pb-2 font-medium text-right">Tickets</th>
                <th className="pb-2 font-medium text-right">Cancelled</th>
                <th className="pb-2 font-medium text-right">Gross</th><th className="pb-2 font-medium text-right">Refunds</th>
                <th className="pb-2 font-medium text-right">Net revenue</th>
                <th className="pb-2 font-medium text-right" title="From reviewers who booked this show">Rating</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {d.shows.map(s => (
                <tr key={s.show_id} className="border-t border-slate-800">
                  <td className="py-2.5 whitespace-nowrap">
                    {dateTime(s.start_time)}
                    {s.show_id === d.best_show_id && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">🏆 Best</span>}
                    {s.upcoming && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300">Upcoming</span>}
                  </td>
                  <td className="py-2.5 text-slate-400">{s.venue} · {s.screen}</td>
                  <td className="py-2.5"><PricingBadge dynamic={s.dynamic_pricing} /></td>
                  <td className="py-2.5 text-right">{s.base_price ? inr(s.base_price) : "—"}</td>
                  <td className="py-2.5 text-right whitespace-nowrap">
                    {s.avg_ticket_price === null ? "—" : inr(s.avg_ticket_price)}
                    {s.avg_ticket_price !== null && s.base_price > 0 && Math.abs(s.avg_ticket_price - s.base_price) >= 1 && (
                      <span className={`ml-1 text-[11px] ${s.avg_ticket_price > s.base_price ? "text-amber-300" : "text-emerald-400"}`}>
                        {s.avg_ticket_price > s.base_price ? "▲" : "▼"}{Math.round(Math.abs(s.avg_ticket_price - s.base_price) / s.base_price * 100)}%
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 pl-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${Math.min(100, s.occupancy)}%`,
                          background: s.occupancy >= 80 ? C.green : s.occupancy >= 40 ? C.blue : C.amber,
                        }} />
                      </div>
                      <span className="text-xs text-slate-400 whitespace-nowrap">{s.occupancy}%</span>
                    </div>
                  </td>
                  <td className="py-2.5 text-right">{num(s.tickets)}</td>
                  <td className="py-2.5 text-right">{num(s.cancelled)}</td>
                  <td className="py-2.5 text-right">{inr(s.gross_revenue)}</td>
                  <td className="py-2.5 text-right text-red-300/80">{s.refunds ? `−${inr(s.refunds)}` : "—"}</td>
                  <td className="py-2.5 text-right text-white">{inr(s.revenue)}</td>
                  <td className="py-2.5 text-right whitespace-nowrap">
                    {s.rating === null ? "—" : <>⭐ {s.rating}<span className="text-slate-500 text-[11px]"> ({s.rating_count})</span></>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty text="No shows of this event in this period." />}

      {d.latest_reviews.length > 0 && (
        <>
          <h3 className="text-sm font-semibold text-slate-300 mt-6 mb-3">Latest reviews</h3>
          <ul className="grid md:grid-cols-2 gap-3">
            {d.latest_reviews.map((r, i) => (
              <li key={i} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-white text-sm truncate">{r.headline}</p>
                  <span className="text-xs text-amber-300 whitespace-nowrap">⭐ {r.rating}/10</span>
                </div>
                <p className="text-xs text-slate-400 mt-1 line-clamp-3">{r.content}</p>
                <p className="text-[11px] text-slate-500 mt-1">
                  {r.author}{r.at ? ` · ${new Date(r.at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function ManagerAnalyticsPage() {
  const { user, loading: authLoading, isManager, isAdmin } = useAuth();
  const router = useRouter();

  const [days, setDays] = useState(30);
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [useCustom, setUseCustom] = useState(false);
  const [eventId, setEventId] = useState("");
  const [data, setData] = useState<ManagerAnalytics | null>(null);
  const [detail, setDetail] = useState<EventAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = useCustom && custom.start && custom.end
        ? { start: custom.start, end: custom.end, event_id: eventId || undefined }
        : { days, event_id: eventId || undefined };
      // Load both independently: if one fails, the other still updates the page
      const [overview, eventDetail] = await Promise.allSettled([
        analyticsApi.get(q),
        eventId ? analyticsApi.event(eventId, q) : Promise.resolve(null),
      ]);
      if (overview.status === "fulfilled") setData(overview.value);
      else toast.error(overview.reason?.message || "Could not load analytics");
      if (eventDetail.status === "fulfilled") setDetail(eventDetail.value);
      else {
        setDetail(null);
        toast.error("Could not load this event's details. If you use an ad blocker, allow localhost.");
      }
    } catch (err: any) {
      toast.error(typeof err?.message === "string" ? err.message : "Could not load analytics");
    } finally {
      setLoading(false);
    }
  }, [days, custom, useCustom, eventId]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/auth/login?redirect=/manager/analytics"); return; }
    if (!isManager && !isAdmin) { router.push("/"); return; }
    load();
  }, [authLoading, user, isManager, isAdmin, load, router]);

  const outcomeData = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.outcomes)
      .map(([k, v]) => ({ key: k, name: OUTCOME_STYLE[k]?.label ?? k, value: v, color: OUTCOME_STYLE[k]?.color ?? C.muted }))
      .filter(x => x.value > 0);
  }, [data]);
  const outcomeTotal = outcomeData.reduce((s, x) => s + x.value, 0);

  const pricingData = useMemo(() => {
    if (!data) return [];
    const { dynamic, fixed } = data.pricing_comparison;
    return [
      { metric: "Occupancy %", Dynamic: dynamic.occupancy, Fixed: fixed.occupancy },
      { metric: "Avg ticket ₹", Dynamic: dynamic.avg_ticket_price, Fixed: fixed.avg_ticket_price },
    ];
  }, [data]);

  const exportCsv = () => {
    if (!data) return;
    const rows = [
      ["Event", "Type", "Gross revenue (INR)", "Net revenue (INR)", "Avg ticket (INR)", "Tickets", "Shows in period", "Occupancy %", "Avg rating (/10)", "Reviews", "Wishlisted"],
      ...data.by_event.map(e => [e.title, e.event_type, e.gross_revenue, e.revenue, e.avg_ticket_price ?? "", e.tickets, e.shows, e.occupancy ?? "", e.rating ?? "", e.reviews, e.wishlisted]),
    ];
    const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `ticketflow-analytics_${data.range.start}_to_${data.range.end}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openEvent = (id: string) => {
    setEventId(id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (authLoading || (loading && !data)) {
    return <div className="text-center py-20 text-slate-500">Loading analytics...</div>;
  }
  if (!data) return <div className="text-center py-20 text-red-400">Could not load analytics.</div>;

  const s = data.summary;
  const { dynamic, fixed } = data.pricing_comparison;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <Link href="/manager" className="text-sm text-slate-400 hover:text-blue-400">← Manager Dashboard</Link>
      <div className="flex flex-wrap items-end justify-between gap-4 mt-2 mb-6">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-blue-400">Analytics</p>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">Sales &amp; Audience Insights</h1>
          <p className="text-sm text-slate-400 mt-1">
            {shortDate(data.range.start)} – {shortDate(data.range.end)} · {data.scope}
            {loading && <span className="ml-2 text-slate-500">Updating…</span>}
          </p>
        </div>
        <button onClick={exportCsv} className="btn-secondary text-sm" disabled={!data.by_event.length}>
          ⬇ Export CSV
        </button>
      </div>

      {!data.has_organization && (
        <div className="card p-4 mb-6 text-sm text-amber-300 border-amber-500/30">
          You don&apos;t have an organization yet, so there is nothing to analyse.{" "}
          <Link href="/verification/organizer" className="underline">Complete organizer verification</Link> to start listing events.
        </div>
      )}

      {/* Filters */}
      <div className="card p-4 mb-6 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Date range">
          {RANGES.map(r => (
            <button key={r.days}
              onClick={() => { setUseCustom(false); setDays(r.days); }}
              className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                !useCustom && days === r.days ? "bg-blue-600 text-white border-blue-600" : "bg-slate-900 text-slate-300 border-slate-700 hover:border-blue-500"}`}>
              {r.label}
            </button>
          ))}
          <button onClick={() => setUseCustom(true)}
            className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
              useCustom ? "bg-blue-600 text-white border-blue-600" : "bg-slate-900 text-slate-300 border-slate-700 hover:border-blue-500"}`}>
            Custom
          </button>
        </div>
        {useCustom && (
          <div className="flex items-center gap-2">
            <input type="date" className="input !min-h-0 !py-1.5 text-sm w-auto" value={custom.start}
              max={custom.end || undefined} onChange={e => setCustom(c => ({ ...c, start: e.target.value }))} aria-label="Start date" />
            <span className="text-slate-500 text-sm">to</span>
            <input type="date" className="input !min-h-0 !py-1.5 text-sm w-auto" value={custom.end}
              min={custom.start || undefined} onChange={e => setCustom(c => ({ ...c, end: e.target.value }))} aria-label="End date" />
          </div>
        )}
        <select className="input !min-h-0 !py-1.5 text-sm w-auto ml-auto" value={eventId}
          onChange={e => setEventId(e.target.value)} aria-label="Filter by event">
          <option value="">All events</option>
          {data.events.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
        </select>
      </div>

      {eventId && detail && <EventDetail d={detail} onBack={() => setEventId("")} />}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <Stat icon="💰" label="Revenue" value={inr(s.revenue)} change={s.revenue_change_pct}
          sub={`gross ${inr(s.gross_revenue)} · ${inr(s.refunds)} refunded`} />
        <Stat icon="🎟️" label="Tickets sold" value={num(s.tickets_sold)} change={s.tickets_change_pct}
          sub={s.tickets_sold ? `avg ${inr(s.avg_ticket_price)}` : undefined} />
        <Stat icon="📈" label="Occupancy" value={s.occupancy_pct === null ? "—" : `${s.occupancy_pct}%`}
          sub={`${s.shows_in_period} show${s.shows_in_period === 1 ? "" : "s"} in period`} />
        <Stat icon="↩️" label="Cancellations" value={num(s.cancellations)} sub={`${s.cancellation_rate_pct}% of bookings`} />
        <Stat icon="⭐" label="Avg rating" value={s.avg_rating === null ? "—" : `${s.avg_rating}/10`} sub={`${num(s.reviews)} reviews · all time`} />
        <Stat icon="❤️" label="Wishlisted" value={num(s.wishlisted)} sub="all time" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Stat icon="👥" label="Unique buyers" value={num(s.unique_buyers)}
          sub={`${num(data.customers.new)} new · ${num(data.customers.returning)} returning`} />
        <Stat icon="🧾" label="Avg order value" value={inr(s.avg_order_value)} sub="spent per booking" />
        <Stat icon="👨‍👩‍👧" label="Avg group size" value={s.avg_group_size ? `${s.avg_group_size}` : "—"} sub="tickets per booking" />
        <Stat icon="⏳" label="Booked ahead" value={s.avg_lead_days === null ? "—" : `${s.avg_lead_days} days`}
          sub={data.lead_time.median_days === null ? undefined : `median ${data.lead_time.median_days} days before the show`} />
      </div>

      {/* Insights */}
      <Card title="💡 Insights" className="mb-6">
        <InsightsSlider items={data.alerts} />
      </Card>

      {/* Revenue trend */}
      <Card title="Revenue & tickets over time" className="mb-6">
        {data.trend.some(d => d.revenue || d.tickets) ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data.trend} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.blue} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={C.blue} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} stroke={C.muted} fontSize={11} minTickGap={24} />
                <YAxis yAxisId="rev" tickFormatter={v => inr(v, true)} stroke={C.muted} fontSize={11} width={70} />
                <YAxis yAxisId="tix" orientation="right" stroke={C.muted} fontSize={11} width={40} allowDecimals={false} />
                <Tooltip {...tooltipStyle} labelFormatter={l => shortDate(String(l))}
                  formatter={(v: any, n: any) => (n === "Revenue" ? inr(Number(v)) : num(Number(v)))} />
                <Legend wrapperStyle={{ fontSize: 12, color: C.muted }} />
                <Bar yAxisId="tix" dataKey="tickets" name="Tickets" fill={C.violet} radius={[3, 3, 0, 0]} maxBarSize={14} opacity={0.7} />
                <Area yAxisId="rev" type="monotone" dataKey="revenue" name="Revenue" stroke={C.blue} strokeWidth={2} fill="url(#rev)" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : <Empty />}
      </Card>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        {/* Sales by event */}
        {!eventId && (
        <Card title="Revenue by event" className="lg:col-span-2">
          {data.by_event.some(e => e.revenue) ? (
            <div style={{ height: Math.max(180, Math.min(8, data.by_event.length) * 44) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_event.slice(0, 8)} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={v => inr(v, true)} stroke={C.muted} fontSize={11} />
                  <YAxis type="category" dataKey="title" stroke={C.muted} fontSize={11} width={140}
                    tickFormatter={t => (t.length > 20 ? t.slice(0, 19) + "…" : t)} />
                  <Tooltip {...tooltipStyle} formatter={(v: any) => inr(Number(v))} />
                  <Bar dataKey="revenue" name="Revenue" fill={C.blue} radius={[0, 4, 4, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty />}
        </Card>
        )}

        {/* Booking outcomes */}
        <Card title="Booking outcomes" className={eventId ? "lg:col-span-3" : ""}>
          {outcomeTotal ? (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={outcomeData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={2} stroke="none">
                      {outcomeData.map(o => <Cell key={o.key} fill={o.color} />)}
                    </Pie>
                    <Tooltip {...tooltipStyle} formatter={(v: any) => `${num(Number(v))} (${Math.round(Number(v) / outcomeTotal * 100)}%)`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-1.5 mt-2">
                {outcomeData.map(o => (
                  <li key={o.key} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-slate-300">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: o.color }} />{o.name}
                    </span>
                    <span className="text-slate-400">{num(o.value)} · {Math.round(o.value / outcomeTotal * 100)}%</span>
                  </li>
                ))}
              </ul>
            </>
          ) : <Empty />}
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Best days */}
        <Card title="Tickets by show day">
          {data.by_weekday.some(d => d.tickets) ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_weekday}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="day" stroke={C.muted} fontSize={11} />
                  <YAxis stroke={C.muted} fontSize={11} allowDecimals={false} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => (n === "Revenue" ? inr(Number(v)) : num(Number(v)))} />
                  <Bar dataKey="tickets" name="Tickets" radius={[4, 4, 0, 0]} maxBarSize={36}>
                    {data.by_weekday.map((d, i) => <Cell key={d.day} fill={i >= 4 ? C.amber : C.blue} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty text="No shows in this period yet." />}
          <p className="text-xs text-slate-500 mt-2">Fri–Sun highlighted.</p>
        </Card>

        {/* Time slots */}
        <Card title="Tickets by show time">
          {data.by_time_slot.some(d => d.tickets) ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_time_slot}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="slot" stroke={C.muted} fontSize={11} interval={0} />
                  <YAxis stroke={C.muted} fontSize={11} allowDecimals={false} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => (n === "Revenue" ? inr(Number(v)) : num(Number(v)))} />
                  <Bar dataKey="tickets" name="Tickets" fill={C.green} radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty text="No shows in this period yet." />}
        </Card>
      </div>

      {/* Booking lead time & sales curve */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Card title="How far ahead people book">
          {data.lead_time.buckets.some(b => b.bookings) ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.lead_time.buckets}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" stroke={C.muted} fontSize={11} interval={0} />
                  <YAxis stroke={C.muted} fontSize={11} allowDecimals={false} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v: any, n: any) => [num(Number(v)), n]} />
                  <Bar dataKey="bookings" name="Bookings" fill={C.violet} radius={[4, 4, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty />}
          <p className="text-xs text-slate-500 mt-2">
            {data.lead_time.avg_days === null ? "No bookings in this period." :
              `On average customers book ${data.lead_time.avg_days} days before the show.`}
          </p>
        </Card>
        <Card title="Sales curve (shows already played)">
          {data.sales_curve.some(p => p.pct_sold) ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.sales_curve}>
                  <defs>
                    <linearGradient id="curve" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C.green} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={C.green} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="days_before" stroke={C.muted} fontSize={11}
                    tickFormatter={d => (d === 0 ? "Show day" : `${d}d`)} />
                  <YAxis stroke={C.muted} fontSize={11} width={40} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                  <Tooltip {...tooltipStyle} labelFormatter={d => (Number(d) === 0 ? "By the show" : `${d} days before`)}
                    formatter={(v: any) => [`${v}% of tickets sold`, "Sold"]} />
                  <Area type="monotone" dataKey="pct_sold" stroke={C.green} strokeWidth={2} fill="url(#curve)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <Empty text="No finished shows in this period." />}
          {(() => {
            const week = data.sales_curve.find(p => p.days_before === 7);
            return week && week.pct_sold ? (
              <p className="text-xs text-slate-500 mt-2">A week before the show, {week.pct_sold}% of its tickets are already sold.</p>
            ) : null;
          })()}
        </Card>
      </div>

      {/* Customers */}
      <Card title="Customers" className="mb-6">
        {data.customers.buyers ? (
          <div className="grid md:grid-cols-3 gap-6 items-center">
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  {(() => {
                    const slices = [
                      { name: "New customers", value: data.customers.new, color: C.blue },
                      { name: "Returning customers", value: data.customers.returning, color: C.green },
                    ].filter(x => x.value);
                    return (
                      <Pie data={slices} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={2} stroke="none">
                        {slices.map(x => <Cell key={x.name} fill={x.color} />)}
                      </Pie>
                    );
                  })()}
                  <Tooltip {...tooltipStyle} formatter={(v: any) => `${num(Number(v))} (${Math.round(Number(v) / data.customers.buyers * 100)}%)`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="space-y-3 text-sm">
              <li className="flex justify-between"><span className="text-slate-400"><span className="text-blue-400">●</span> New customers</span>
                <span className="text-white">{num(data.customers.new)}</span></li>
              <li className="flex justify-between"><span className="text-slate-400"><span className="text-emerald-400">●</span> Returning customers</span>
                <span className="text-white">{num(data.customers.returning)}</span></li>
              <li className="flex justify-between border-t border-slate-800 pt-3"><span className="text-slate-400">🔁 Bought 2+ times this period</span>
                <span className="text-white">{num(data.customers.repeat_buyers)} · {data.customers.repeat_rate_pct}%</span></li>
              <li className="flex justify-between"><span className="text-slate-400">🎭 Book more than one category</span>
                <span className="text-white">{num(data.customers.cross_category)} · {data.customers.cross_category_pct}%</span></li>
            </ul>
            <div>
              <p className="text-xs text-slate-500 mb-2">Most common category mixes</p>
              {data.customers.top_combos.length ? (
                <ul className="space-y-1.5">
                  {data.customers.top_combos.map(c => (
                    <li key={c.combo} className="flex justify-between text-sm">
                      <span className="text-slate-300">{c.combo}</span>
                      <span className="text-slate-400">{num(c.customers)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-slate-500">Customers stick to one category.</p>}
            </div>
          </div>
        ) : <Empty />}
        <p className="text-xs text-slate-500 mt-3">New = first booking with you was in this period. Returning = booked with you before.</p>
      </Card>

      {/* Dynamic vs fixed */}
      <Card title="Dynamic vs fixed pricing (shows in this period)" className="mb-6">
        {dynamic.shows || fixed.shows ? (
          <div className="grid md:grid-cols-2 gap-6 items-center">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pricingData}>
                  <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="metric" stroke={C.muted} fontSize={11} />
                  <YAxis stroke={C.muted} fontSize={11} width={45} />
                  <Tooltip {...tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 12, color: C.muted }} />
                  <Bar dataKey="Dynamic" fill={C.blue} radius={[4, 4, 0, 0]} maxBarSize={40} />
                  <Bar dataKey="Fixed" fill={C.muted} radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 text-xs text-left">
                  <th className="py-2 font-medium"></th><th className="py-2 font-medium">⚡ Dynamic</th><th className="py-2 font-medium">Fixed</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {([
                  ["Shows", num(dynamic.shows), num(fixed.shows)],
                  ["Tickets", num(dynamic.tickets), num(fixed.tickets)],
                  ["Revenue", inr(dynamic.revenue), inr(fixed.revenue)],
                  ["Occupancy", `${dynamic.occupancy}%`, `${fixed.occupancy}%`],
                  ["Avg ticket", inr(dynamic.avg_ticket_price), inr(fixed.avg_ticket_price)],
                ] as const).map(([k, a, b]) => (
                  <tr key={k} className="border-t border-slate-800">
                    <td className="py-2 text-slate-500">{k}</td><td className="py-2">{a}</td><td className="py-2">{b}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No shows in this period yet." />}
      </Card>

      {/* Upcoming shows */}
      <Card title="Upcoming shows" className="mb-6">
        {data.upcoming_shows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead>
                <tr className="text-slate-500 text-xs text-left">
                  <th className="pb-2 font-medium">Show</th><th className="pb-2 font-medium">When</th>
                  <th className="pb-2 font-medium">Pricing</th><th className="pb-2 font-medium text-right pr-3">Base price</th>
                  <th className="pb-2 font-medium w-48">Seats sold</th><th className="pb-2 font-medium text-right">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {data.upcoming_shows.map(u => (
                  <tr key={u.show_id} className="border-t border-slate-800">
                    <td className="py-2.5 pr-3">
                      <p className="text-white font-medium">{u.title}</p>
                      <p className="text-xs text-slate-500">{u.venue} · {u.screen}</p>
                    </td>
                    <td className="py-2.5 pr-3 text-slate-300 whitespace-nowrap">{dateTime(u.start_time)}</td>
                    <td className="py-2.5 pr-3"><PricingBadge dynamic={u.dynamic_pricing} /></td>
                    <td className="py-2.5 pr-3 text-right text-slate-300">{u.base_price ? inr(u.base_price) : "—"}</td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden" role="progressbar"
                          aria-valuenow={u.occupancy} aria-valuemin={0} aria-valuemax={100} aria-label={`${u.title} occupancy`}>
                          <div className="h-full rounded-full" style={{
                            width: `${Math.min(100, u.occupancy)}%`,
                            background: u.occupancy >= 80 ? C.green : u.occupancy >= 40 ? C.blue : C.amber,
                          }} />
                        </div>
                        <span className="text-xs text-slate-400 whitespace-nowrap">{num(u.sold)}/{num(u.capacity)}</span>
                      </div>
                    </td>
                    <td className="py-2.5 text-right text-slate-300">{inr(u.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No upcoming shows." />}
      </Card>

      {/* Per-event table */}
      <Card title="Events in detail">
        {data.by_event.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[880px]">
              <thead>
                <tr className="text-slate-500 text-xs text-left">
                  <th className="pb-2 font-medium">Event</th><th className="pb-2 font-medium text-right">Gross</th>
                  <th className="pb-2 font-medium text-right">Net revenue</th>
                  <th className="pb-2 font-medium text-right">Avg ticket</th>
                  <th className="pb-2 font-medium text-right">Tickets</th><th className="pb-2 font-medium text-right">Shows</th>
                  <th className="pb-2 font-medium text-right">Occupancy</th><th className="pb-2 font-medium text-right">Rating</th>
                  <th className="pb-2 font-medium text-right">Wishlisted</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {data.by_event.map(e => (
                  <tr key={e.event_id} className="border-t border-slate-800 hover:bg-slate-800/40 cursor-pointer"
                    onClick={() => openEvent(e.event_id)} title="Open this event's analytics">
                    <td className="py-2.5">
                      <button type="button" className="text-white hover:text-blue-400 text-left"
                        onClick={ev => { ev.stopPropagation(); openEvent(e.event_id); }}>
                        {e.title} ›
                      </button>
                      <span className="ml-2 text-xs text-slate-500 capitalize">{e.event_type}</span>
                    </td>
                    <td className="py-2.5 text-right">{inr(e.gross_revenue)}</td>
                    <td className="py-2.5 text-right text-white">{inr(e.revenue)}</td>
                    <td className="py-2.5 text-right">{e.avg_ticket_price === null ? "—" : inr(e.avg_ticket_price)}</td>
                    <td className="py-2.5 text-right">{num(e.tickets)}</td>
                    <td className="py-2.5 text-right">{num(e.shows)}</td>
                    <td className="py-2.5 text-right">{e.occupancy === null ? "—" : `${e.occupancy}%`}</td>
                    <td className="py-2.5 text-right">{e.rating === null ? "—" : `${e.rating}/10`}</td>
                    <td className="py-2.5 text-right">{num(e.wishlisted)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty />}
        <p className="text-xs text-slate-500 mt-3">
          Click an event to see its own analytics. Gross = everything paid; Net revenue = gross minus refunds. Tickets = confirmed bookings. Occupancy covers shows starting in this period.
        </p>
      </Card>
    </div>
  );
}
