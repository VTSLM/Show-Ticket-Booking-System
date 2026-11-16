"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import toast from "react-hot-toast";
import { browseApi } from "@/lib/api";
import ShowDetailsView from "@/components/ShowDetailsView";

export default function ShowDetailsPage() {
  const { showId } = useParams<{ showId: string }>();
  const [show, setShow] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    browseApi
      .showDetail(showId)
      .then((data) => {
        if (isMounted) setShow(data);
      })
      .catch((err: any) => {
        if (isMounted) toast.error(err.message || "Failed to load show details");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [showId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090b12] text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
          <p className="text-sm font-medium">Loading show details…</p>
        </div>
      </div>
    );
  }

  if (!show) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#090b12] px-4 text-center text-slate-300">
        <p className="text-4xl">🎬</p>
        <h1 className="mt-4 text-2xl font-bold text-white">Show Not Found</h1>
        <p className="mt-2 text-sm text-slate-400">
          The requested show could not be found or is no longer scheduled.
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

  return <ShowDetailsView showData={show} preselectedShowId={showId} />;
}
