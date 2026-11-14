"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";

export default function BrowsePage() {
  const [shows, setShows] = useState<any[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    city: "",
    event_type: "",
    search: "",
  });

  const load = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filters.city) params.city = filters.city;
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.search) params.search = filters.search;
      const data = await browseApi.shows(params);
      setShows(data);
    } catch (error: any) {
      toast.error(error.message || "Failed to load shows");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    browseApi.cities().then(setCities).catch(() => {});
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateFilter =
    (key: string) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setFilters((current) => ({ ...current, [key]: event.target.value }));
    };

  const formatDate = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch { return timestamp; }
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch { return ""; }
  };

  const typeLabel: Record<string, string> = {
    movie: "Movie",
    concert: "Concert",
    theatre: "Theatre",
    other: "Show",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--background, #090b12)",
        color: "var(--foreground, #f4f6fb)",
      }}
    >
      {/* ── Hero ── */}
      <div
        style={{
          background:
            "linear-gradient(180deg, #0d1120 0%, var(--background, #090b12) 100%)",
          borderBottom: "1px solid var(--border, #292e3d)",
          padding: "48px 24px 36px",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <p
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              color: "var(--blue, #287cff)",
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            Find your next experience
          </p>
          <h1
            style={{
              fontSize: "clamp(2rem, 5vw, 3rem)",
              fontWeight: 800,
              letterSpacing: "-0.02em",
              margin: "0 0 8px",
              color: "var(--foreground, #f4f6fb)",
            }}
          >
            Movies &amp; Shows
          </h1>
          <p style={{ color: "var(--muted, #9ba3b5)", fontSize: 15, margin: 0 }}>
            Discover what's playing near you.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
        {/* ── Filter bar ── */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr auto auto auto",
            gap: 10,
            marginBottom: 36,
            background: "var(--surface, #11141e)",
            border: "1px solid var(--border, #292e3d)",
            borderRadius: 16,
            padding: "14px 16px",
          }}
          className="filter-bar"
        >
          <input
            style={{
              background: "var(--surface-raised, #181c28)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 10,
              color: "var(--foreground, #f4f6fb)",
              padding: "10px 14px",
              fontSize: 14,
              outline: "none",
              width: "100%",
              minWidth: 0,
            }}
            placeholder="Search movies or venues…"
            value={filters.search}
            onChange={updateFilter("search")}
            onKeyDown={(e) => { if (e.key === "Enter") load(); }}
            aria-label="Search shows or venues"
          />
          <select
            style={{
              background: "var(--surface-raised, #181c28)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 10,
              color: "var(--foreground, #f4f6fb)",
              padding: "10px 14px",
              fontSize: 14,
              outline: "none",
              cursor: "pointer",
            }}
            value={filters.city}
            onChange={updateFilter("city")}
            aria-label="Filter by city"
          >
            <option value="">All cities</option>
            {cities.map((city) => (
              <option key={city} value={city}>{city}</option>
            ))}
          </select>
          <select
            style={{
              background: "var(--surface-raised, #181c28)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 10,
              color: "var(--foreground, #f4f6fb)",
              padding: "10px 14px",
              fontSize: 14,
              outline: "none",
              cursor: "pointer",
            }}
            value={filters.event_type}
            onChange={updateFilter("event_type")}
            aria-label="Filter by type"
          >
            <option value="">All types</option>
            {["movie", "concert", "theatre", "other"].map((type) => (
              <option key={type} value={type}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </option>
            ))}
          </select>
          <button
            onClick={load}
            style={{
              background: "var(--blue, #287cff)",
              color: "#fff",
              border: "none",
              borderRadius: 10,
              padding: "10px 22px",
              fontSize: 14,
              fontWeight: 700,
              cursor: "pointer",
              whiteSpace: "nowrap",
              transition: "opacity 0.15s",
            }}
            onMouseEnter={(e) => ((e.target as HTMLElement).style.opacity = "0.85")}
            onMouseLeave={(e) => ((e.target as HTMLElement).style.opacity = "1")}
          >
            Search
          </button>
        </div>

        {/* ── Results header ── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Now showing</h2>
          {!loading && (
            <span
              style={{
                background: "var(--surface, #11141e)",
                border: "1px solid var(--border, #292e3d)",
                borderRadius: 999,
                padding: "3px 12px",
                fontSize: 12,
                color: "var(--muted, #9ba3b5)",
              }}
            >
              {shows.length} {shows.length === 1 ? "show" : "shows"}
            </span>
          )}
        </div>

        {/* ── States ── */}
        {loading ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 20,
            }}
          >
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                style={{
                  background: "var(--surface, #11141e)",
                  border: "1px solid var(--border, #292e3d)",
                  borderRadius: 16,
                  overflow: "hidden",
                  animation: "pulse 1.5s ease-in-out infinite",
                }}
              >
                <div style={{ height: 220, background: "var(--surface-raised, #181c28)" }} />
                <div style={{ padding: 18 }}>
                  <div style={{ height: 18, width: "60%", background: "var(--surface-raised, #181c28)", borderRadius: 6, marginBottom: 10 }} />
                  <div style={{ height: 13, width: "80%", background: "var(--surface-raised, #181c28)", borderRadius: 6, marginBottom: 6 }} />
                  <div style={{ height: 13, width: "50%", background: "var(--surface-raised, #181c28)", borderRadius: 6 }} />
                </div>
              </div>
            ))}
          </div>
        ) : shows.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "80px 24px",
              background: "var(--surface, #11141e)",
              border: "1px solid var(--border, #292e3d)",
              borderRadius: 20,
            }}
          >
            <div style={{ fontSize: 56, marginBottom: 16 }} aria-hidden="true">🎬</div>
            <p style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No shows found</p>
            <p style={{ color: "var(--muted, #9ba3b5)", fontSize: 14 }}>
              Try a different search or filter.
            </p>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 20,
            }}
          >
            {shows.map((show) => (
              <Link
                key={show.show_id}
                href={`/shows/${show.show_id}/seats`}
                style={{ textDecoration: "none", display: "block" }}
                className="show-card"
              >
                <div
                  style={{
                    background: "var(--surface, #11141e)",
                    border: "1px solid var(--border, #292e3d)",
                    borderRadius: 16,
                    overflow: "hidden",
                    transition: "transform 0.2s, border-color 0.2s, box-shadow 0.2s",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                  }}
                  className="show-card-inner"
                >
                  {/* Poster */}
                  <div style={{ position: "relative", height: 220, overflow: "hidden" }}>
                    {show.poster_url ? (
                      <img
                        src={show.poster_url}
                        alt={`${show.title} poster`}
                        style={{
                          width: "100%",
                          height: "100%",
                          objectFit: "cover",
                          transition: "transform 0.3s",
                        }}
                        className="show-poster"
                      />
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          height: "100%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background:
                            "linear-gradient(135deg, #0d1120 0%, #131929 50%, #0a0f1c 100%)",
                          fontSize: 56,
                        }}
                      >
                        🎥
                      </div>
                    )}
                    {/* Type badge */}
                    <span
                      style={{
                        position: "absolute",
                        top: 12,
                        right: 12,
                        background: "rgba(9,11,18,0.82)",
                        backdropFilter: "blur(6px)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "3px 10px",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#c8d0e0",
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                      }}
                    >
                      {typeLabel[show.event_type] || show.event_type || "Show"}
                    </span>
                  </div>

                  {/* Info */}
                  <div style={{ padding: "16px 18px 18px", flex: 1, display: "flex", flexDirection: "column" }}>
                    <h3
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        color: "var(--foreground, #f4f6fb)",
                        margin: "0 0 4px",
                        lineHeight: 1.3,
                      }}
                      className="show-title"
                    >
                      {show.title}
                    </h3>
                    {show.language && (
                      <p style={{ fontSize: 12, color: "var(--muted, #9ba3b5)", margin: "0 0 10px" }}>
                        {show.language}
                      </p>
                    )}

                    <div style={{ marginTop: "auto" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
                        <span style={{ fontSize: 13 }}>📍</span>
                        <span style={{ fontSize: 13, color: "#c8d0e0" }}>
                          {show.venue_name}{show.city ? `, ${show.city}` : ""}
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
                        <span style={{ fontSize: 13 }}>🕐</span>
                        <span style={{ fontSize: 13, color: "var(--muted, #9ba3b5)" }}>
                          {formatDate(show.start_time)} · {formatTime(show.start_time)}
                        </span>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          borderTop: "1px solid var(--border, #292e3d)",
                          paddingTop: 12,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 20,
                            fontWeight: 800,
                            color: "var(--blue, #287cff)",
                            letterSpacing: "-0.01em",
                          }}
                        >
                          ₹{show.base_price}
                        </span>
                        <span
                          style={{
                            fontSize: 12,
                            color:
                              show.available_seats > 20
                                ? "#00c977"
                                : show.available_seats > 5
                                ? "#ffb300"
                                : "#ff4455",
                            fontWeight: 600,
                          }}
                        >
                          {show.available_seats ?? "—"} seats
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .show-card:hover .show-card-inner {
          transform: translateY(-4px);
          border-color: rgba(40, 124, 255, 0.5) !important;
          box-shadow: 0 12px 40px rgba(40, 124, 255, 0.12);
        }
        .show-card:hover .show-title {
          color: var(--blue, #287cff) !important;
        }
        .show-card:hover .show-poster {
          transform: scale(1.04);
        }
        @media (max-width: 700px) {
          .filter-bar {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
