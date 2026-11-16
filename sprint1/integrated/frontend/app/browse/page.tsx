"use client";
import { useState, useEffect } from "react";
import { browseApi } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";

export default function BrowsePage() {
  const [shows, setShows] = useState<any[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ city: "", event_type: "", search: "" });

  const load = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filters.city) params.city = filters.city;
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.search) params.search = filters.search;
      const data = await browseApi.shows(params);
      setShows(data);
    } catch (e: any) {
      toast.error(e.message || "Failed to load shows");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    browseApi.cities().then(setCities).catch(() => {});
    load();
  }, []);

  const fh = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setFilters(f => ({ ...f, [k]: e.target.value }));

  const formatTime = (ts: string) => {
    try { return new Date(ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }); }
    catch { return ts; }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6 text-[#1a1a2e]">Browse Shows</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 mb-6 flex flex-wrap gap-3">
        <input className="input flex-1 min-w-[180px]" placeholder="Search shows or venue..."
          value={filters.search} onChange={fh("search")} />
        <select className="input w-40" value={filters.city} onChange={fh("city")}>
          <option value="">All Cities</option>
          {cities.map(c => <option key={c}>{c}</option>)}
        </select>
        <select className="input w-40" value={filters.event_type} onChange={fh("event_type")}>
          <option value="">All Types</option>
          {["movie","concert","theatre","other"].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={load} className="btn-primary">Search</button>
      </div>

      {/* Results */}
      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading shows...</div>
      ) : shows.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-5xl mb-4">🎭</p>
          <p>No shows found. Try different filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {shows.map(show => (
            <Link key={show.show_id} href={`/shows/${show.show_id}/seats`}
              className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow group">
              {show.poster_url ? (
                <img src={show.poster_url} alt={show.title} className="w-full h-48 object-cover" />
              ) : (
                <div className="w-full h-48 bg-gradient-to-br from-[#1a1a2e] to-[#e94560] flex items-center justify-center">
                  <span className="text-5xl">🎬</span>
                </div>
              )}
              <div className="p-4">
                <h3 className="font-bold text-lg group-hover:text-red-500 transition-colors">{show.title}</h3>
                <p className="text-sm text-gray-500">{show.event_type} • {show.language || "—"}</p>
                <p className="text-sm text-gray-600 mt-1">📍 {show.venue_name}, {show.city}</p>
                <p className="text-sm text-gray-600">🕐 {formatTime(show.start_time)}</p>
                <div className="flex items-center justify-between mt-3">
                  <span className="text-red-500 font-bold">₹{show.base_price}</span>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    show.available_seats > 10 ? "bg-green-100 text-green-700" :
                    show.available_seats > 0 ? "bg-yellow-100 text-yellow-700" :
                    "bg-red-100 text-red-700"
                  }`}>
                    {show.available_seats ?? "?"} seats
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
