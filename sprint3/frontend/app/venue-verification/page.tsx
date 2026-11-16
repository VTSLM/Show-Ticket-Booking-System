"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { venueDocumentsApi, venueVerificationApi } from "@/lib/api";

type VenueDraft = {
  name: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  licensed_capacity: number | null;
  license_expiry: string;
  noc_expiry: string;
};

type Application = VenueDraft & {
  id: string;
  status: string;
  version: number;
  reviewer_comments?: string | null;
};

const emptyDraft: VenueDraft = {
  name: "",
  address: "",
  city: "",
  state: "",
  pincode: "",
  licensed_capacity: null,
  license_expiry: "",
  noc_expiry: "",
};

const inputClass =
  "mt-1 block w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20";

export default function VenueVerificationPage() {
  const { isManager, isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [applications, setApplications] = useState<Application[]>([]);
  const [draft, setDraft] = useState<VenueDraft>(emptyDraft);
  const [editingId, setEditingId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadApplications() {
    try {
      const result = await venueVerificationApi.mine();
      setApplications(result);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not load applications"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading) return;

    if (isAdmin) {
      router.replace("/admin/venue-reviews");
      return;
    }

    if (!isManager) {
      router.replace("/");
      return;
    }

    void loadApplications();
  }, [authLoading, isManager, isAdmin, router]);

  function updateField(field: keyof VenueDraft, value: string | number | null) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function startEditing(application: Application) {
    setEditingId(application.id);
    setDraft({
      name: application.name || "",
      address: application.address || "",
      city: application.city || "",
      state: application.state || "",
      pincode: application.pincode || "",
      licensed_capacity: application.licensed_capacity ?? null,
      license_expiry: application.license_expiry || "",
      noc_expiry: application.noc_expiry || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function clearForm() {
    setEditingId("");
    setDraft(emptyDraft);
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);

    try {
      const payload = {
        ...draft,
        pincode: draft.pincode || undefined,
        licensed_capacity: draft.licensed_capacity ?? null,
        license_expiry: draft.license_expiry || null,
        noc_expiry: draft.noc_expiry || null,
      };

      if (editingId) {
        await venueVerificationApi.update(editingId, payload);
        toast.success("Venue application updated");
      } else {
        const created = await venueVerificationApi.create(payload);
        toast.success("Venue draft created");
        if (created?.id) setEditingId(created.id);
      }

      await loadApplications();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save draft");
    } finally {
      setSaving(false);
    }
  }

  async function submitApplication(caseId: string) {
    try {
      await venueVerificationApi.submit(caseId);
      toast.success("Application submitted for review");
      clearForm();
      await loadApplications();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not submit application"
      );
    }
  }

  async function uploadFile(kind: "venue_photo" | "seating_plan", file?: File) {
    if (!editingId || !file) {
      toast.error("Save the draft before attaching files");
      return;
    }

    try {
      await venueDocumentsApi.upload(editingId, kind, file);
      toast.success(kind === "venue_photo" ? "Venue photo attached" : "Seating plan attached");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    }
  }

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-slate-950 px-4 text-slate-300">
        <p>Loading venue applications…</p>
      </div>
    );
  }

  return (
    <main className="min-h-[calc(100vh-64px)] bg-slate-950 px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-5xl">
        <header className="mb-8">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-blue-400">
            Manager workspace
          </p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Venue verification
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400 sm:text-base">
            Add venue details, attach a venue photo and seating plan, and submit it for review.
          </p>
        </header>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl sm:p-7">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">
                {editingId ? "Edit venue application" : "New venue application"}
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Fill in the venue details and attach the required proof before submitting.
              </p>
            </div>

            {editingId && (
              <button
                type="button"
                onClick={clearForm}
                className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
              >
                Start a new application
              </button>
            )}
          </div>

          <form onSubmit={saveDraft} className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <label className="block text-sm font-medium text-slate-300 md:col-span-2">
              Venue name <span className="text-red-400">*</span>
              <input
                required
                minLength={2}
                maxLength={200}
                className={inputClass}
                placeholder="Example: Central Cinema"
                value={draft.name}
                onChange={(event) => updateField("name", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300 md:col-span-2">
              Address
              <input
                className={inputClass}
                placeholder="Street address or mall"
                value={draft.address}
                onChange={(event) => updateField("address", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              City <span className="text-red-400">*</span>
              <input
                required
                minLength={2}
                maxLength={100}
                className={inputClass}
                placeholder="City"
                value={draft.city}
                onChange={(event) => updateField("city", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              State
              <input
                className={inputClass}
                placeholder="State"
                value={draft.state}
                onChange={(event) => updateField("state", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              PIN code
              <input
                className={inputClass}
                placeholder="PIN code"
                value={draft.pincode}
                onChange={(event) => updateField("pincode", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              Licensed capacity
              <input
                type="number"
                min={1}
                className={inputClass}
                placeholder="e.g. 300"
                value={draft.licensed_capacity ?? ""}
                onChange={(event) =>
                  updateField(
                    "licensed_capacity",
                    event.target.value ? Number(event.target.value) : null
                  )
                }
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              Licence expiry
              <input
                type="date"
                className={inputClass}
                value={draft.license_expiry}
                onChange={(event) => updateField("license_expiry", event.target.value)}
              />
            </label>

            <label className="block text-sm font-medium text-slate-300">
              NOC expiry
              <input
                type="date"
                className={inputClass}
                value={draft.noc_expiry}
                onChange={(event) => updateField("noc_expiry", event.target.value)}
              />
            </label>

            <div className="flex items-end gap-3 md:col-span-2">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Saving…" : editingId ? "Update draft" : "Save draft"}
              </button>
            </div>
          </form>

          {editingId && (
            <div className="mt-8 grid gap-4 border-t border-slate-800 pt-6 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-300">
                Venue photo
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className={inputClass}
                  onChange={(event) =>
                    uploadFile("venue_photo", event.target.files?.[0])
                  }
                />
              </label>

              <label className="block text-sm font-medium text-slate-300">
                Seating plan
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className={inputClass}
                  onChange={(event) =>
                    uploadFile("seating_plan", event.target.files?.[0])
                  }
                />
              </label>
            </div>
          )}
        </section>

        <section>
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">
                Your applications
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {applications.length} {applications.length === 1 ? "application" : "applications"}
              </p>
            </div>

            <button
              type="button"
              onClick={() => void loadApplications()}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
            >
              Refresh
            </button>
          </div>

          {applications.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 px-5 py-10 text-center">
              <p className="font-medium text-slate-200">No applications yet</p>
              <p className="mt-2 text-sm text-slate-400">
                Create a venue application using the form above.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {applications.map((application) => {
                const editable = ["draft", "changes_requested"].includes(application.status);
                return (
                  <article
                    key={application.id}
                    className="rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-lg sm:p-6"
                  >
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <h3 className="break-words text-lg font-semibold text-white">
                          {application.name}
                        </h3>
                        <p className="mt-1 break-words text-sm text-slate-400">
                          {[application.address, application.city, application.state]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>

                        <div className="mt-3 flex flex-wrap gap-2">
                          <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold capitalize text-blue-300">
                            {String(application.status).replaceAll("_", " ")}
                          </span>
                          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs text-slate-300">
                            Version {application.version}
                          </span>
                        </div>

                        {application.reviewer_comments && (
                          <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                            <p className="text-xs font-bold uppercase tracking-wide text-amber-300">
                              Reviewer comments
                            </p>
                            <p className="mt-1 whitespace-pre-wrap break-words text-sm text-amber-100">
                              {application.reviewer_comments}
                            </p>
                          </div>
                        )}
                      </div>

                      {editable && (
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => startEditing(application)}
                            className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => void submitApplication(application.id)}
                            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
                          >
                            Submit for review
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}