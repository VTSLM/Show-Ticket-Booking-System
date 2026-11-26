"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { browseApi, recommendationsApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import ShowDetailsView from "@/components/ShowDetailsView";

export default function EventDetailsPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const searchParams = useSearchParams();
  const preselectedShowId = searchParams.get("show_id") || undefined;

  const [eventData, setEventData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const uid = user?.uid;
  const loadedEventId = eventData ? eventId : null; // set once the published event loaded

  // Browsing behaviour for recommendations (#218): count one view per page open
  useEffect(() => {
    if (!uid || !loadedEventId) return;
    recommendationsApi.recordView(String(loadedEventId)).catch(() => {});
  }, [uid, loadedEventId]);

  useEffect(() => {
    let isMounted = true;
    browseApi
      .eventDetail(eventId)
      .then((data) => {
        if (isMounted) setEventData(data);
      })
      .catch((err: any) => {
        if (isMounted) toast.error(err.message || "Failed to load event details");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [eventId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090b12] text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          <p className="text-sm font-medium">Loading event details…</p>
        </div>
      </div>
    );
  }

  if (!eventData) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#090b12] px-4 text-center text-slate-300">
        <p className="text-4xl">🎭</p>
        <h1 className="mt-4 text-2xl font-bold text-white">Event Not Found</h1>
        <p className="mt-2 text-sm text-slate-400">
          The requested event could not be found or has not been published yet.
        </p>
        <a
          href="/browse"
          className="mt-6 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500"
        >
          Return to Browse
        </a>
      </div>
    );
  }

  return (
    <ShowDetailsView
      showData={eventData}
      preselectedShowId={preselectedShowId}
      isEventMode={true}
    />
  );
}
