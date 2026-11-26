"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { recommendationsApi, type UserPreferences } from "@/lib/api";

const MAX_ITEMS = 10;
const MAX_LENGTH = 40;

type Field = "genres" | "artists" | "cities";

const FIELDS: { key: Field; label: string; placeholder: string }[] = [
  { key: "genres", label: "Favourite genres", placeholder: "e.g. Thriller" },
  { key: "artists", label: "Favourite artists", placeholder: "e.g. A. R. Rahman" },
  { key: "cities", label: "Cities you go out in", placeholder: "e.g. Ahmedabad" },
];

const EMPTY: UserPreferences = { genres: [], artists: [], cities: [] };

function same(a: UserPreferences, b: UserPreferences) {
  return FIELDS.every(({ key }) => a[key].join("\n") === b[key].join("\n"));
}

function ChipInput({
  id,
  label,
  placeholder,
  values,
  options,
  onChange,
}: {
  id: string;
  label: string;
  placeholder: string;
  values: string[];
  options: string[];
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const full = values.length >= MAX_ITEMS;
  const suggestions = useMemo(() => {
    const taken = new Set(values.map((v) => v.toLowerCase()));
    const q = draft.trim().toLowerCase();
    return options
      .filter((o) => !taken.has(o.toLowerCase()) && (!q || o.toLowerCase().includes(q)))
      .slice(0, 8);
  }, [options, values, draft]);

  const add = (raw: string) => {
    const v = raw.replace(/\s+/g, " ").trim().slice(0, MAX_LENGTH);
    if (!v || full || values.some((x) => x.toLowerCase() === v.toLowerCase())) return;
    onChange([...values, v]);
    setDraft("");
  };

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-200">
        {label} <span className="text-slate-500">({values.length}/{MAX_ITEMS})</span>
      </label>
      <div className="flex flex-wrap gap-2">
        {values.map((v) => (
          <span
            key={v}
            className="flex items-center gap-1 rounded-full border border-blue-800 bg-blue-950/50 px-3 py-1 text-xs text-blue-100"
          >
            {v}
            <button
              type="button"
              aria-label={`Remove ${v}`}
              className="ml-1 text-blue-300 hover:text-white"
              onClick={() => onChange(values.filter((x) => x !== v))}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <input
        id={id}
        className="input mt-2"
        placeholder={full ? "Maximum reached" : placeholder}
        value={draft}
        disabled={full}
        maxLength={MAX_LENGTH}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add(draft);
          }
        }}
      />
      {!full && suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="rounded-full border border-slate-700 px-2.5 py-0.5 text-xs text-slate-300 hover:border-blue-500 hover:text-white"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Favourite genres, artists and cities used for recommendations (#218, FR2). */
export default function PreferencesForm() {
  const [saved, setSaved] = useState<UserPreferences>(EMPTY);
  const [prefs, setPrefs] = useState<UserPreferences>(EMPTY);
  const [options, setOptions] = useState<Record<Field, string[]>>({ genres: [], artists: [], cities: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    recommendationsApi
      .preferences()
      .then((p) => {
        const clean = { genres: p.genres, artists: p.artists, cities: p.cities };
        setSaved(clean);
        setPrefs(clean);
      })
      .catch((err) => toast.error(err.message || "Could not load your preferences"))
      .finally(() => setLoading(false));
    recommendationsApi
      .preferenceOptions()
      .then(setOptions)
      .catch(() => {}); // suggestions are optional
  }, []);

  const changed = !same(prefs, saved);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const p = await recommendationsApi.savePreferences(prefs);
      const clean = { genres: p.genres, artists: p.artists, cities: p.cities };
      setSaved(clean);
      setPrefs(clean);
      toast.success("Preferences saved. Your recommendations will use them.");
    } catch (err: any) {
      toast.error(err.message || "Could not save your preferences");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form id="preferences" onSubmit={save} className="card mt-6 space-y-5 p-6" noValidate>
      <div>
        <h2 className="text-lg font-semibold text-white">Your preferences</h2>
        <p className="text-sm text-slate-400">
          Used for the &ldquo;Recommended for you&rdquo; picks on the home page.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : (
        FIELDS.map(({ key, label, placeholder }) => (
          <ChipInput
            key={key}
            id={`pref-${key}`}
            label={label}
            placeholder={placeholder}
            values={prefs[key]}
            options={options[key] || []}
            onChange={(values) => setPrefs((p) => ({ ...p, [key]: values }))}
          />
        ))
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="btn-secondary"
          disabled={!changed || saving}
          onClick={() => setPrefs(saved)}
        >
          Cancel
        </button>
        <button type="submit" className="btn-primary disabled:opacity-60" disabled={!changed || saving}>
          {saving ? "Saving..." : "Save preferences"}
        </button>
      </div>
    </form>
  );
}
