"use client";

import React, { useEffect, useState } from "react";
import { fetchHealth } from "../lib/api";
import Link from "next/link";

interface NavbarProps {
  onOpenCreateVenue: () => void;
  onOpenCreateEvent: () => void;
  onOpenCreateShow: () => void;
}

export default function Navbar({
  onOpenCreateVenue,
  onOpenCreateEvent,
  onOpenCreateShow,
}: NavbarProps) {
  const [dbStatus, setDbStatus] = useState<string>("checking");
  const [dbConnected, setDbConnected] = useState<boolean>(false);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        if (data.database && data.database.database_connected) {
          setDbStatus("Connected");
          setDbConnected(true);
        } else if (data.database && data.database.status === "unconfigured") {
          setDbStatus("No DB URL");
          setDbConnected(false);
        } else {
          setDbStatus("Offline");
          setDbConnected(false);
        }
      })
      .catch(() => {
        setDbStatus("Offline");
        setDbConnected(false);
      });
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-blue-900/30 bg-[#090d1a]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand & Reference Header */}
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-blue-700 to-blue-500 shadow-glow text-white font-black text-lg group-hover:scale-105 transition-transform">
              🎬
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-black tracking-wider text-white">
                  CINEMA<span className="text-blue-500">OPS</span>
                </span>
                <span className="rounded-full border border-blue-500/40 bg-blue-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-400">
                  Manager
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-400">
                Show Scheduling & Event Management
              </p>
            </div>
          </Link>
        </div>

        {/* Status Indicators & Actions */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* Database Health Pill */}
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-800 bg-[#0d1326] px-3.5 py-1.5 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${dbConnected ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-amber-400"
                }`}
            />
            <span className="text-slate-400 font-medium">DB:</span>
            <span className={dbConnected ? "font-bold text-emerald-400" : "font-bold text-amber-400"}>
              {dbStatus}
            </span>
          </div>

          {/* Action Buttons matching the reference blue styling */}
          <button
            onClick={onOpenCreateVenue}
            className="rounded-2xl border border-blue-500/30 bg-blue-950/40 px-3.5 py-2.5 text-xs font-bold text-blue-400 hover:border-blue-500 hover:text-white transition-all shadow-sm flex items-center gap-1.5"
          >
            <span>🏛️</span>
            <span>+ Add Cinema</span>
          </button>
          <button
            onClick={onOpenCreateEvent}
            className="rounded-2xl border border-slate-700/80 bg-slate-900/80 px-4 py-2.5 text-xs font-bold text-slate-200 hover:border-blue-500 hover:text-white transition-all shadow-sm"
          >
            + New Movie
          </button>
          <button
            onClick={onOpenCreateShow}
            className="rounded-2xl bg-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-glow hover:bg-blue-500 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            + Schedule Show
          </button>
        </div>
      </div>
    </header>
  );
}
