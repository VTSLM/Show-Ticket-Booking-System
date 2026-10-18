// src/lib/api.ts
// Thin wrapper around fetch for calls to the FastAPI backend.

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export type StakeholderRole = "customer" | "manager" | "admin";

// -------------------------------------------------------------------------
// Registration
// -------------------------------------------------------------------------

export interface RegisterPayload {
  firebase_token: string;
  name: string;
  email: string;
  phone?: string;
  requested_role: StakeholderRole;
}

export interface RegisterResponse {
  user_id: string;
  name: string;
  email: string;
  role: string;
  status: "active" | "pending_approval";
  message: string;
}

export async function registerUser(payload: RegisterPayload): Promise<RegisterResponse> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? "Registration failed");
  }
  return res.json();
}

// -------------------------------------------------------------------------
// Verify token / login
// -------------------------------------------------------------------------

export interface UserProfile {
  user_id: string;
  firebase_uid: string;
  name: string;
  email: string;
  phone: string | null;
  roles: string[];
  status: string;
  redirect_to: string;
}

export interface VerifyTokenResponse {
  user: UserProfile;
}

export async function verifyToken(firebase_token: string): Promise<VerifyTokenResponse> {
  const res = await fetch(`${BASE_URL}/auth/verify-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ firebase_token }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? "Token verification failed");
  }
  return res.json();
}

// -------------------------------------------------------------------------
// Admin: pending approvals
// -------------------------------------------------------------------------

export interface PendingUser {
  user_id: string;
  name: string;
  email: string;
  requested_role: string;
  created_at: string;
}

export async function fetchPendingUsers(token: string): Promise<PendingUser[]> {
  const res = await fetch(`${BASE_URL}/auth/admin/pending`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch pending users");
  const data = await res.json();
  return data.pending;
}

export async function approveUser(
  token: string,
  userId: string,
  action: "approve" | "reject"
): Promise<void> {
  const res = await fetch(`${BASE_URL}/auth/admin/pending/${userId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? "Action failed");
  }
}
