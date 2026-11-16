// Edit profile info — API helpers (backend: routers/profile.py)
import { api } from "./api";
import { auth } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface MyProfile {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  birthdate: string | null;   // YYYY-MM-DD
  bio: string | null;
  avatar_url: string | null;
  status: string;
  created_at: string;
  roles: string[];
}

export interface ProfileUpdate {
  name?: string;
  phone?: string;
  birthdate?: string;
  bio?: string;
}

export const profileApi = {
  get: () => api.get<MyProfile>("/api/profile"),
  update: (body: ProfileUpdate) => api.patch<MyProfile>("/api/profile", body),
  removePhoto: () => api.delete<MyProfile>("/api/profile/photo"),

  // Multipart upload (the shared api helper always sends JSON)
  uploadPhoto: async (file: File): Promise<MyProfile> => {
    const token = await auth.currentUser?.getIdToken();
    if (!token) throw new Error("Not authenticated");
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/api/profile/photo`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : "Could not upload photo");
    }
    return res.json();
  },
};

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const PHOTO_MAX_BYTES = 2 * 1024 * 1024;

export const BIO_MAX = 300;
