"use client";

import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import StatsBar from "../components/StatsBar";
import EventList from "../components/EventList";
import ShowList from "../components/ShowList";
import CreateEventModal from "../components/CreateEventModal";
import CreateShowModal from "../components/CreateShowModal";
import CreateVenueModal from "../components/CreateVenueModal";
import { fetchEvents, fetchShows, fetchVenues } from "../lib/api";
import { EventItem, ShowItem, VenueItem } from "../lib/types";

export default function ManagerDashboard() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [shows, setShows] = useState<ShowItem[]>([]);
  const [venues, setVenues] = useState<VenueItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"events" | "shows">("shows");

  // Modals state
  const [isVenueModalOpen, setIsVenueModalOpen] = useState(false);
  const [isEventModalOpen, setIsEventModalOpen] = useState(false);
  const [isShowModalOpen, setIsShowModalOpen] = useState(false);
  const [selectedEventForShow, setSelectedEventForShow] = useState<string | undefined>(undefined);

  // Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  function showToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [eventsData, showsData, venuesData] = await Promise.all([
        fetchEvents().catch(() => []),
        fetchShows().catch(() => []),
        fetchVenues().catch(() => []),
      ]);

      setEvents(eventsData);
      setShows(showsData);
      setVenues(venuesData);
    } catch (err: any) {
      setError(
        "Could not load data from the backend API. Please make sure the FastAPI server is running."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  function handleVenueCreated(newVenue: VenueItem) {
    setVenues((prev) => [...prev, newVenue]);
    showToast(`Cinema venue "${newVenue.name}" successfully created!`);
  }

  function handleEventCreated(newEvent: EventItem) {
    setEvents((prev) => [newEvent, ...prev]);
    showToast(`Event "${newEvent.title}" successfully saved to Supabase!`);
  }

  function handleShowCreated(newShow: ShowItem) {
    setShows((prev) => [newShow, ...prev]);
    showToast(`Show successfully scheduled!`);
  }

  function openShowModalWithEvent(eventId: string) {
    setSelectedEventForShow(eventId);
    setIsShowModalOpen(true);
  }

  return (
    <div className="min-h-screen bg-[#050711] text-slate-100 flex flex-col">
      {/* Navbar matching reference */}
      <Navbar
        onOpenCreateVenue={() => setIsVenueModalOpen(true)}
        onOpenCreateEvent={() => setIsEventModalOpen(true)}
        onOpenCreateShow={() => {
          setSelectedEventForShow(undefined);
          setIsShowModalOpen(true);
        }}
      />

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 rounded-2xl bg-blue-600 px-5 py-3.5 text-xs font-bold text-white shadow-glow border border-blue-400/40 animate-bounce">
          ✓ {toastMessage}
        </div>
      )}

      {/* Main Content */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header Greeting */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]" />
              <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                Cinema Operations
              </span>
            </div>
            <h1 className="mt-1 text-3xl sm:text-4xl font-black tracking-tight text-white">
              Movie & Show Schedule Manager
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Inspired by modern cinema experiences. Create movies, schedule auditoriums, and hand off to seat pricing.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              className="rounded-2xl border border-slate-800 bg-[#0d1326] px-4 py-2.5 text-xs font-bold text-slate-300 hover:border-blue-500 hover:text-white transition-all shadow-sm"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* Stats Metrics Bar */}
        <StatsBar events={events} shows={shows} venues={venues} />

        {/* Error / DB Configuration Banner */}
        {error && (
          <div className="rounded-2xl border border-amber-500/40 bg-amber-950/40 p-4 text-xs text-amber-200 flex items-center justify-between shadow-card">
            <div className="flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="font-bold">{error}</p>
                <p className="text-amber-300/80 mt-0.5">
                  Start the FastAPI backend on <code>http://localhost:8000</code> with <code>DATABASE_URL</code> configured in <code>backend/.env</code>.
                </p>
              </div>
            </div>
            <button
              onClick={loadData}
              className="rounded-xl bg-amber-500/20 px-3.5 py-2 text-amber-200 font-bold hover:bg-amber-500/30 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Modern Pill Tab Switcher */}
        <div className="flex items-center justify-between border-b border-blue-900/30 pb-4">
          <div className="flex items-center gap-2 rounded-2xl bg-[#090d1a] p-1.5 border border-slate-800">
            <button
              onClick={() => setActiveTab("shows")}
              className={`rounded-xl px-5 py-2 text-xs font-bold transition-all ${
                activeTab === "shows"
                  ? "bg-blue-600 text-white shadow-glow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              🎟️ Scheduled Shows ({shows.length})
            </button>
            <button
              onClick={() => setActiveTab("events")}
              className={`rounded-xl px-5 py-2 text-xs font-bold transition-all ${
                activeTab === "events"
                  ? "bg-blue-600 text-white shadow-glow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              🎬 Movie Catalogue ({events.length})
            </button>
          </div>

          <div className="hidden sm:block">
            {activeTab === "shows" ? (
              <button
                onClick={() => {
                  setSelectedEventForShow(undefined);
                  setIsShowModalOpen(true);
                }}
                className="text-xs font-bold text-blue-400 hover:text-blue-300"
              >
                + Schedule New Show
              </button>
            ) : (
              <button
                onClick={() => setIsEventModalOpen(true)}
                className="text-xs font-bold text-blue-400 hover:text-blue-300"
              >
                + Add Movie to Catalogue
              </button>
            )}
          </div>
        </div>

        {/* Tab View */}
        {activeTab === "shows" ? (
          <ShowList
            shows={shows}
            loading={loading}
            onOpenCreateShow={() => {
              setSelectedEventForShow(undefined);
              setIsShowModalOpen(true);
            }}
          />
        ) : (
          <EventList
            events={events}
            loading={loading}
            onSelectEventForShow={openShowModalWithEvent}
            onOpenCreateEvent={() => setIsEventModalOpen(true)}
          />
        )}
      </main>

      {/* Modals */}
      <CreateVenueModal
        isOpen={isVenueModalOpen}
        onClose={() => setIsVenueModalOpen(false)}
        onVenueCreated={handleVenueCreated}
      />

      <CreateEventModal
        isOpen={isEventModalOpen}
        onClose={() => setIsEventModalOpen(false)}
        onEventCreated={handleEventCreated}
      />

      <CreateShowModal
        isOpen={isShowModalOpen}
        onClose={() => setIsShowModalOpen(false)}
        events={events}
        venues={venues}
        initialEventId={selectedEventForShow}
        onShowCreated={handleShowCreated}
      />
    </div>
  );
}
