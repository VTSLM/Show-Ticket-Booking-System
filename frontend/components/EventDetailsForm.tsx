"use client";

// Full event details for managers (#169): one form for creating and for editing an event.
// Fields follow the event type: movies get release date, certificate, formats and cast & crew;
// concerts, theatre and other live events get artists / performers instead.

import { useRef, useState } from "react";
import toast from "react-hot-toast";
import { managerApi } from "@/lib/api";

const C = {
  raised: "#181c28",
  border: "#292e3d",
  blue: "#287cff",
  fg: "#f4f6fb",
  muted: "#9ba3b5",
  red: "#ff4455",
};

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

const EVENT_TYPES = ["movie", "concert", "theatre", "other"];
const CERTIFICATES = ["U", "UA", "A", "S"];
const FORMATS = ["2D", "3D", "IMAX", "IMAX 3D", "4DX"];

type Person = { name: string; role: string };

export interface EventFormValues {
  title: string;
  event_type: string;
  language: string;
  duration_minutes: string;
  genre: string;
  description: string;
  poster_url: string;
  backdrop_url: string;
  release_date: string;
  certificate: string;
  formats: string[];
  cast_crew: Person[];
  artists: Person[];
  terms_and_conditions: string;
}

// The manager event list returns JSON columns as text; accept both
function people(value: unknown): Person[] {
  let v = value;
  if (typeof v === "string") {
    try { v = JSON.parse(v); } catch { return []; }
  }
  if (!Array.isArray(v)) return [];
  return v
    .filter((p) => p && typeof p === "object")
    .map((p: any) => ({ name: String(p.name ?? ""), role: String(p.role ?? p.character ?? "") }));
}

export function eventToFormValues(ev?: any): EventFormValues {
  return {
    title: ev?.title ?? "",
    event_type: ev?.event_type ?? "movie",
    language: ev?.language ?? "",
    duration_minutes: ev?.duration_minutes ? String(ev.duration_minutes) : "",
    genre: ev?.genre ?? "",
    description: ev?.description ?? "",
    poster_url: ev?.poster_url ?? "",
    backdrop_url: ev?.backdrop_url ?? "",
    release_date: ev?.release_date ? String(ev.release_date).slice(0, 10) : "",
    certificate: ev?.certificate ?? "UA",
    formats: Array.isArray(ev?.formats) && ev.formats.length ? ev.formats : ["2D"],
    cast_crew: people(ev?.cast_crew),
    artists: people(ev?.artists),
    terms_and_conditions: ev?.terms_and_conditions ?? "",
  };
}

// What is sent to the backend: movie-only fields are left out for live events
export function formValuesToPayload(v: EventFormValues) {
  const isMovie = v.event_type === "movie";
  const clean = (list: Person[]) =>
    list.map((p) => ({ name: p.name.trim(), role: p.role.trim() })).filter((p) => p.name);
  return {
    title: v.title.trim(),
    event_type: v.event_type,
    language: v.language.trim() || null,
    duration_minutes: parseInt(v.duration_minutes) || null,
    genre: v.genre.trim() || null,
    description: v.description.trim() || null,
    poster_url: v.poster_url.trim() || null,
    backdrop_url: v.backdrop_url.trim() || null,
    terms_and_conditions: v.terms_and_conditions.trim() || null,
    cast_crew: isMovie ? clean(v.cast_crew) : [],
    artists: isMovie ? [] : clean(v.artists),
    ...(isMovie
      ? { release_date: v.release_date || "", certificate: v.certificate || "UA", formats: v.formats.length ? v.formats : ["2D"] }
      : { release_date: "", certificate: null, formats: [] }),
  };
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ display: "block", fontSize: 11, fontWeight: 600, color: C.muted, marginBottom: 6, letterSpacing: "0.06em", textTransform: "uppercase" }}>
      {children}
    </span>
  );
}

function Field({ label, children, wide }: { label: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <label style={{ gridColumn: wide ? "1 / -1" : undefined, display: "block" }}>
      <Label>{label}</Label>
      {children}
    </label>
  );
}

function ImagePicker({
  kind, label, value, onChange,
}: { kind: "poster" | "backdrop"; label: string; value: string; onChange: (url: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const pick = async (file?: File) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error("Image must be 5 MB or smaller"); return; }
    setBusy(true);
    try {
      const { url } = await managerApi.uploadEventImage(kind, file);
      onChange(url);
      toast.success(`${label} uploaded`);
    } catch (err: any) {
      toast.error(err.message || `Could not upload the ${kind}`);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  const isPoster = kind === "poster";
  return (
    <div data-testid={`${kind}-picker`}>
      <Label>{label}</Label>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{
          width: isPoster ? 90 : 160, height: isPoster ? 135 : 90, flexShrink: 0, borderRadius: 8,
          border: `1px dashed ${C.border}`, background: C.raised, overflow: "hidden",
          display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontSize: 11,
        }}>
          {value
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={value} alt={`${label} preview`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            : "No image"}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: "none" }}
            onChange={(e) => pick(e.target.files?.[0])} aria-label={`Upload ${kind}`} />
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={() => input.current?.click()} disabled={busy}
              style={{ ...inputStyle, width: "auto", cursor: busy ? "wait" : "pointer", fontWeight: 700 }}>
              {busy ? "Uploading…" : value ? "Replace" : "Upload"}
            </button>
            {value && (
              <button type="button" onClick={() => onChange("")}
                style={{ ...inputStyle, width: "auto", cursor: "pointer", color: C.red }}>
                Remove
              </button>
            )}
          </div>
          <input style={inputStyle} placeholder="…or paste an image URL" value={value}
            onChange={(e) => onChange(e.target.value)} aria-label={`${label} URL`} />
          <span style={{ fontSize: 11, color: C.muted }}>
            JPG, PNG or WebP, up to 5 MB. {isPoster ? "Portrait (2:3) works best." : "Wide (16:9) works best."}
          </span>
        </div>
      </div>
    </div>
  );
}

function PeopleList({
  label, testId, rolePlaceholder, value, onChange,
}: { label: string; testId: string; rolePlaceholder: string; value: Person[]; onChange: (v: Person[]) => void }) {
  const set = (i: number, key: keyof Person, text: string) =>
    onChange(value.map((p, j) => (j === i ? { ...p, [key]: text } : p)));
  return (
    <div style={{ gridColumn: "1 / -1" }} data-testid={testId}>
      <Label>{label}</Label>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {value.map((p, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}>
            <input style={inputStyle} placeholder="Name" value={p.name} onChange={(e) => set(i, "name", e.target.value)} />
            <input style={inputStyle} placeholder={rolePlaceholder} value={p.role} onChange={(e) => set(i, "role", e.target.value)} />
            <button type="button" aria-label={`Remove ${p.name || "row"}`} onClick={() => onChange(value.filter((_, j) => j !== i))}
              style={{ ...inputStyle, width: 40, cursor: "pointer", color: C.red }}>✕</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...value, { name: "", role: "" }])}
          style={{ ...inputStyle, cursor: "pointer", color: C.blue, fontWeight: 700, borderStyle: "dashed" }}>
          + Add {label.toLowerCase().includes("artist") ? "artist" : "person"}
        </button>
      </div>
    </div>
  );
}

export default function EventDetailsForm({
  initial, submitLabel, onSubmit, onCancel, children,
}: {
  initial: EventFormValues;
  submitLabel: string;
  onSubmit: (payload: ReturnType<typeof formValuesToPayload>) => Promise<void>;
  onCancel?: () => void;
  children?: React.ReactNode; // extra fields shown first (e.g. host organization)
}) {
  const [v, setV] = useState<EventFormValues>(initial);
  const [saving, setSaving] = useState(false);
  const set = <K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) => setV((cur) => ({ ...cur, [key]: value }));
  const isMovie = v.event_type === "movie";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit(formValuesToPayload(v));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} data-testid="event-details-form" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      {children}
      <Field label="Title">
        <input style={inputStyle} value={v.title} onChange={(e) => set("title", e.target.value)} required />
      </Field>
      <Field label="Type">
        <select style={inputStyle} value={v.event_type} onChange={(e) => set("event_type", e.target.value)}>
          {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
        </select>
      </Field>
      <Field label="Language">
        <input style={inputStyle} value={v.language} onChange={(e) => set("language", e.target.value)} />
      </Field>
      <Field label="Duration (min)">
        <input style={inputStyle} type="number" min={1} value={v.duration_minutes} onChange={(e) => set("duration_minutes", e.target.value)} />
      </Field>
      <Field label={isMovie ? "Genre" : "Category / Genre"} wide>
        <input style={inputStyle} placeholder={isMovie ? "e.g. Action, Drama" : "e.g. Bollywood, Stand-up, Musical"}
          value={v.genre} onChange={(e) => set("genre", e.target.value)} />
      </Field>
      <Field label="About the event" wide>
        <textarea style={{ ...inputStyle, minHeight: 90, resize: "vertical" }} value={v.description}
          onChange={(e) => set("description", e.target.value)} />
      </Field>

      <ImagePicker kind="poster" label="Poster" value={v.poster_url} onChange={(url) => set("poster_url", url)} />
      <ImagePicker kind="backdrop" label="Backdrop" value={v.backdrop_url} onChange={(url) => set("backdrop_url", url)} />

      {isMovie ? (
        <>
          <Field label="Release date">
            <input style={inputStyle} type="date" value={v.release_date} onChange={(e) => set("release_date", e.target.value)} />
          </Field>
          <Field label="Certificate">
            <select style={inputStyle} value={v.certificate} onChange={(e) => set("certificate", e.target.value)}>
              {CERTIFICATES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <div style={{ gridColumn: "1 / -1" }} data-testid="formats">
            <Label>Formats</Label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {FORMATS.map((f) => {
                const on = v.formats.includes(f);
                return (
                  <label key={f} style={{
                    ...inputStyle, width: "auto", cursor: "pointer", display: "inline-flex", gap: 6, alignItems: "center",
                    borderColor: on ? C.blue : C.border, color: on ? C.fg : C.muted,
                  }}>
                    <input type="checkbox" checked={on}
                      onChange={() => set("formats", on ? v.formats.filter((x) => x !== f) : [...v.formats, f])} />
                    {f}
                  </label>
                );
              })}
            </div>
          </div>
          <PeopleList label="Cast & crew" testId="cast-crew" rolePlaceholder="Role (e.g. Director, Paul Atreides)"
            value={v.cast_crew} onChange={(list) => set("cast_crew", list)} />
        </>
      ) : (
        <PeopleList label="Artists / performers" testId="artists" rolePlaceholder="Role (e.g. Headliner, Lead actor)"
          value={v.artists} onChange={(list) => set("artists", list)} />
      )}

      <Field label="Terms and conditions" wide>
        <textarea style={{ ...inputStyle, minHeight: 70, resize: "vertical" }} value={v.terms_and_conditions}
          placeholder="e.g. Entry 30 minutes before the start. No outside food." onChange={(e) => set("terms_and_conditions", e.target.value)} />
      </Field>

      <div style={{ gridColumn: "1 / -1", display: "flex", gap: 10 }}>
        <button type="submit" disabled={saving} style={{
          flex: 1, background: C.blue, color: "#fff", border: "none", borderRadius: 10, padding: "12px",
          fontSize: 14, fontWeight: 700, cursor: saving ? "wait" : "pointer", opacity: saving ? 0.7 : 1,
        }}>
          {saving ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} style={{ ...inputStyle, width: "auto", padding: "12px 20px", cursor: "pointer" }}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
