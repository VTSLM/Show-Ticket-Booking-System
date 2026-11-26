"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { profileApi, MyProfile, BIO_MAX, PHOTO_TYPES, PHOTO_MAX_BYTES } from "@/lib/profileApi";
import PreferencesForm from "@/components/PreferencesForm";

type Form = { name: string; phone: string; birthdate: string; bio: string };

const toForm = (p: MyProfile): Form => ({
  name: p.name || "",
  phone: p.phone || "",
  birthdate: p.birthdate ? p.birthdate.slice(0, 10) : "",
  bio: p.bio || "",
});

const ROLE_LABELS: Record<string, string> = { customer: "Customer", manager: "Manager", admin: "Admin" };

export default function ProfilePage() {
  const { user, loading: authLoading, refreshProfile } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [form, setForm] = useState<Form>({ name: "", phone: "", birthdate: "", bio: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (!authLoading && !user) { router.push("/auth/login?redirect=/profile"); return; }
    if (user) {
      profileApi
        .get()
        .then(p => { setProfile(p); setForm(toForm(p)); })
        .catch(err => toast.error(err.message || "Could not load your profile"))
        .finally(() => setLoading(false));
    }
  }, [user, authLoading, router]);

  const set = (field: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm(f => ({ ...f, [field]: e.target.value }));
    setErrors(er => ({ ...er, [field]: undefined }));
  };

  const validate = () => {
    const e: Partial<Record<keyof Form, string>> = {};
    const name = form.name.trim().replace(/\s+/g, " ");
    if (name.length < 2) e.name = "Name must be at least 2 characters.";
    else if (!/^[A-Za-z][A-Za-z .'\-]*$/.test(name)) e.name = "Use letters, spaces, dots, apostrophes or hyphens only.";
    const phone = form.phone.replace(/[\s-]/g, "").replace(/^\+91/, "");
    if (phone && !/^[6-9]\d{9}$/.test(phone)) e.phone = "Enter a valid 10-digit Indian mobile number.";
    if (!form.birthdate) e.birthdate = "Birthdate is required.";
    else if (form.birthdate > today) e.birthdate = "Birthdate cannot be in the future.";
    if (form.bio.length > BIO_MAX) e.bio = `Bio must be at most ${BIO_MAX} characters.`;
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const changed = profile !== null && JSON.stringify(form) !== JSON.stringify(toForm(profile));

  const handleSave = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!profile || !validate()) return;
    const original = toForm(profile);
    const body: Record<string, string> = {};
    (Object.keys(form) as (keyof Form)[]).forEach(k => {
      if (form[k] !== original[k]) body[k] = k === "name" ? form.name.trim().replace(/\s+/g, " ") : form[k];
    });
    if (Object.keys(body).length === 0) return;

    setSaving(true);
    try {
      const updated = await profileApi.update(body);
      setProfile(updated);
      setForm(toForm(updated));
      await refreshProfile();           // update the name shown in the navbar
      toast.success("Profile updated");
    } catch (err: any) {
      toast.error(err.message || "Could not update your profile");
    } finally {
      setSaving(false);
    }
  };

  const handlePhotoChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";                         // allow choosing the same file again
    if (!file) return;
    if (!PHOTO_TYPES.includes(file.type)) { toast.error("Choose a JPG, PNG or WebP image."); return; }
    if (file.size > PHOTO_MAX_BYTES) { toast.error("Photo must be 2 MB or smaller."); return; }
    setPhotoBusy(true);
    try {
      const updated = await profileApi.uploadPhoto(file);
      setProfile(updated);
      await refreshProfile();
      toast.success("Profile photo updated");
    } catch (err: any) {
      toast.error(err.message || "Could not upload photo");
    } finally {
      setPhotoBusy(false);
    }
  };

  const handlePhotoRemove = async () => {
    if (!confirm("Remove your profile photo?")) return;
    setPhotoBusy(true);
    try {
      const updated = await profileApi.removePhoto();
      setProfile(updated);
      await refreshProfile();
      toast.success("Profile photo removed");
    } catch (err: any) {
      toast.error(err.message || "Could not remove photo");
    } finally {
      setPhotoBusy(false);
    }
  };

  if (loading || authLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>;
  if (!profile) return <div className="text-center py-20 text-red-400">Profile not found.</div>;

  const initials = profile.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const memberSince = new Date(profile.created_at).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold tracking-tight text-white mb-6">My Profile</h1>

      <div className="card p-6 mb-6 flex items-center gap-4">
        <div className="flex flex-col items-center gap-2 shrink-0">
          {profile.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={profile.avatar_url} alt="Your profile photo"
              className="h-20 w-20 rounded-full object-cover border border-slate-700" />
          ) : (
            <div className="h-20 w-20 rounded-full bg-blue-600 flex items-center justify-center text-2xl font-bold text-white" aria-hidden="true">
              {initials}
            </div>
          )}
          <input ref={fileInput} type="file" accept={PHOTO_TYPES.join(",")} className="hidden"
            onChange={handlePhotoChosen} aria-label="Choose profile photo" />
          <div className="flex gap-2 text-xs">
            <button type="button" className="text-blue-400 hover:underline disabled:opacity-50"
              disabled={photoBusy} onClick={() => fileInput.current?.click()}>
              {photoBusy ? "Saving..." : profile.avatar_url ? "Change" : "Add photo"}
            </button>
            {profile.avatar_url && !photoBusy && (
              <button type="button" className="text-slate-400 hover:text-red-400 hover:underline" onClick={handlePhotoRemove}>
                Remove
              </button>
            )}
          </div>
        </div>
        <div className="min-w-0">
          <p className="text-lg font-semibold text-white truncate">{profile.name}</p>
          <p className="text-sm text-slate-400 truncate">{profile.email}</p>
          <div className="mt-1 flex flex-wrap gap-2 items-center">
            {profile.roles.map(r => (
              <span key={r} className="text-xs px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300">{ROLE_LABELS[r] || r}</span>
            ))}
            <span className="text-xs text-slate-500">Member since {memberSince}</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleSave} className="card p-6 space-y-5" noValidate>
        <h2 className="text-lg font-semibold text-white">Edit profile info</h2>

        <div>
          <label htmlFor="name" className="block text-sm font-medium text-slate-200 mb-1">Full name</label>
          <input id="name" className="input" value={form.name} onChange={set("name")} maxLength={80} autoComplete="name" />
          {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name}</p>}
        </div>

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-200 mb-1">Email</label>
          <input id="email" className="input opacity-60 cursor-not-allowed" value={profile.email} disabled readOnly />
          <p className="text-xs text-slate-500 mt-1">Your email is used to log in and can&apos;t be changed here.</p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-slate-200 mb-1">
              Phone <span className="text-slate-500">(optional)</span>
            </label>
            <input id="phone" className="input" type="tel" inputMode="numeric" placeholder="10-digit mobile number"
              value={form.phone} onChange={set("phone")} maxLength={16} autoComplete="tel" />
            {errors.phone && <p className="text-xs text-red-400 mt-1">{errors.phone}</p>}
          </div>
          <div>
            <label htmlFor="birthdate" className="block text-sm font-medium text-slate-200 mb-1">Birthdate</label>
            <input id="birthdate" className="input" type="date" max={today} value={form.birthdate} onChange={set("birthdate")} />
            {errors.birthdate && <p className="text-xs text-red-400 mt-1">{errors.birthdate}</p>}
          </div>
        </div>

        <div>
          <label htmlFor="bio" className="block text-sm font-medium text-slate-200 mb-1">
            Bio <span className="text-slate-500">(optional)</span>
          </label>
          <textarea id="bio" className="input min-h-[100px]" placeholder="Tell others a little about yourself"
            value={form.bio} onChange={set("bio")} maxLength={BIO_MAX} />
          <div className="flex justify-between text-xs mt-1">
            <span className="text-red-400">{errors.bio}</span>
            <span className="text-slate-500">{form.bio.length}/{BIO_MAX}</span>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" disabled={!changed || saving}
            onClick={() => { setForm(toForm(profile)); setErrors({}); }}>
            Cancel
          </button>
          <button type="submit" className="btn-primary disabled:opacity-60" disabled={!changed || saving}>
            {saving ? "Saving..." : "Save changes"}
          </button>
        </div>
      </form>

      <PreferencesForm />
    </div>
  );
}
