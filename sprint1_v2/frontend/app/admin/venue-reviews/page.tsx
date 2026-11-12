"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { venueDocumentsApi, venueVerificationApi } from "@/lib/api";

type ReviewCase = {
  id: string;
  venue_id: string;
  name: string;
  city: string;
  status: string;
  version: number;
};

type ScreenCheck = {
  id: string;
  name: string;
  licensed_capacity: number;
  actual_seat_count: number;
  capacity_mismatch: boolean;
};

const secondaryButton =
  "inline-flex min-h-10 items-center justify-center rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50";

export default function VenueReviewsPage() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [queue, setQueue] = useState<ReviewCase[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [screens, setScreens] = useState<ScreenCheck[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function loadQueue() {
    try {
      const result = await venueVerificationApi.queue();
      setQueue(result);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load queue");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading) return;

    if (!isAdmin) {
      router.replace("/");
      return;
    }

    void loadQueue();
  }, [authLoading, isAdmin, router]);

  async function claimAndOpen(caseId: string) {
    setBusy(true);

    try {
      await venueVerificationApi.claim(caseId);

      const [details, history, docs] = await Promise.all([
        venueVerificationApi.details(caseId),
        venueVerificationApi.audit(caseId),
        venueDocumentsApi.list(caseId),
      ]);

      setSelected(details.case);
      setScreens(details.screens || []);
      setDocuments(docs || []);
      setAudit(history || []);
      setReason("");
      await loadQueue();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not claim this case. It may be claimed by another reviewer."
      );
      await loadQueue();
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: string) {
    if (!selected) return;

    if (decision !== "approved" && !reason.trim()) {
      toast.error("Enter a reason for rejection or request changes");
      return;
    }

    setBusy(true);
    try {
      await venueVerificationApi.decide(selected.id, {
        expected_version: selected.version,
        decision,
        reason: reason.trim() || undefined,
      });

      toast.success(`Venue ${decision.replaceAll("_", " ")}`);
      setSelected(null);
      setScreens([]);
      setDocuments([]);
      setAudit([]);
      setReason("");
      await loadQueue();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Decision failed; refresh and retry");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-slate-950 px-4 text-slate-300">
        <p>Loading venue review queue…</p>
      </div>
    );
  }

  return (
    <main className="min-h-[calc(100vh-64px)] bg-slate-950 px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl">
        <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-blue-400">
              Administrator workspace
            </p>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Venue review
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400 sm:text-base">
              Claim a case before reviewing it. A claim is required to make a decision.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void loadQueue()}
            className={secondaryButton}
          >
            Refresh queue
          </button>
        </header>

        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(300px,0.8fr)_minmax(0,1.2fr)]">
          <section className="min-w-0">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Review queue</h2>
              <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                {queue.length} cases
              </span>
            </div>

            {queue.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 p-6 text-center">
                <p className="font-medium text-slate-200">Queue is clear</p>
                <p className="mt-2 text-sm text-slate-400">
                  Submitted applications will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {queue.map((item) => {
                  const active = selected?.id === item.id;
                  return (
                    <article
                      key={item.id}
                      className={`min-w-0 rounded-xl border p-4 transition ${
                        active
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-slate-800 bg-slate-900 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="break-words font-semibold text-white">
                            {item.name}
                          </h3>
                          <p className="mt-1 text-sm text-slate-400">{item.city}</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs capitalize text-slate-300">
                              {item.status.replaceAll("_", " ")}
                            </span>
                          </div>
                        </div>

                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void claimAndOpen(item.id)}
                          className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {active ? "Claimed" : "Claim / review"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl sm:p-7">
            {!selected ? (
              <div className="flex min-h-64 flex-col items-center justify-center text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-xl text-slate-400">
                  ✓
                </div>
                <h2 className="font-semibold text-white">No case selected</h2>
                <p className="mt-2 max-w-sm text-sm leading-6 text-slate-400">
                  Select a case from the queue and claim it to open the review workspace.
                </p>
              </div>
            ) : (
              <div className="space-y-7">
                <div className="border-b border-slate-800 pb-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
                        Venue application
                      </p>
                      <h2 className="mt-2 break-words text-2xl font-bold text-white">
                        {selected.name}
                      </h2>
                      <p className="mt-2 break-words text-sm leading-6 text-slate-400">
                        {[selected.address, selected.city, selected.state, selected.pincode]
                          .filter(Boolean)
                          .join(", ")}
                      </p>
                    </div>

                    <span className="rounded-full border border-green-500/30 bg-green-500/10 px-3 py-1.5 text-xs font-semibold capitalize text-green-300">
                      {selected.status.replaceAll("_", " ")}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm">
                      <span className="text-slate-400">Licensed capacity:</span>{" "}
                      <strong>{selected.licensed_capacity ?? "Not provided"}</strong>
                    </div>
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm">
                      <span className="text-slate-400">License expiry:</span>{" "}
                      <strong>{selected.license_expiry ?? "Not provided"}</strong>
                    </div>
                    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm sm:col-span-2">
                      <span className="text-slate-400">NOC expiry:</span>{" "}
                      <strong>{selected.noc_expiry ?? "Not provided"}</strong>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold text-white">Screen capacity checks</h3>

                  {screens.length === 0 ? (
                    <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">
                      No screen records were found. Verify the venue capacity before approving.
                    </p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      {screens.map((screen) => (
                        <div
                          key={screen.id}
                          className="flex flex-col gap-2 rounded-lg border border-slate-800 bg-slate-950/70 p-4 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0">
                            <p className="break-words font-medium text-slate-100">
                              {screen.name}
                            </p>
                            <p className="mt-1 text-sm text-slate-400">
                              Licensed capacity: {screen.licensed_capacity}
                              <span className="mx-2">·</span>
                              Actual seats: {screen.actual_seat_count}
                            </p>
                          </div>

                          <span
                            className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                              screen.capacity_mismatch
                                ? "bg-red-500/10 text-red-300"
                                : "bg-green-500/10 text-green-300"
                            }`}
                          >
                            {screen.capacity_mismatch ? "Mismatch" : "Matches"}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <h3 className="font-semibold text-white">Attachments</h3>

                  {documents.length === 0 ? (
                    <p className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-200">
                      No venue photo or seating plan attached yet.
                    </p>
                  ) : (
                    documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-950/60 p-3"
                      >
                        <div className="min-w-0">
                          <p className="font-medium text-slate-100">
                            {doc.kind === "venue_photo" ? "Venue photo" : "Seating plan"}
                          </p>
                          <p className="text-sm text-slate-400 break-all">
                            {doc.original_filename}
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            void venueDocumentsApi.download(
                              selected.id,
                              doc.id,
                              doc.original_filename
                            )
                          }
                          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500"
                        >
                          Download
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <label className="block text-sm font-medium text-slate-300">
                  Reviewer reason or comments
                  <textarea
                    className="mt-2 block min-h-28 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-white outline-none placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Required when rejecting or requesting changes"
                  />
                </label>

                <div className="flex flex-col gap-2 border-b border-slate-800 pb-6 sm:flex-row sm:flex-wrap">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void decide("approved")}
                    className="min-h-11 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Approve
                  </button>

                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void decide("changes_requested")}
                    className="min-h-11 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Request changes
                  </button>

                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void decide("rejected")}
                    className="min-h-11 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>

                <div>
                  <h3 className="font-semibold text-white">Audit history</h3>
                  {audit.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-400">
                      No audit entries yet.
                    </p>
                  ) : (
                    <ol className="mt-3 space-y-3">
                      {audit.map((entry) => (
                        <li
                          key={entry.id}
                          className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/70 p-3"
                        >
                          <p className="break-words text-sm font-medium text-slate-200">
                            {entry.action.replaceAll("_", " ")}: {entry.old_status} → {entry.new_status}
                          </p>
                          {entry.reason && (
                            <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-400">
                              {entry.reason}
                            </p>
                          )}
                          <p className="mt-2 text-xs text-slate-500">
                            {entry.created_at
                              ? new Date(entry.created_at).toLocaleString()
                              : ""}
                          </p>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}