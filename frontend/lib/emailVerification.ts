import type { User } from "firebase/auth";
import { sendEmailVerification } from "firebase/auth";

// Email/password accounts must verify their email before using TicketFlow (#208).
// Google accounts come verified. Must match EMAIL_VERIFICATION_REQUIRED on the backend.
export const EMAIL_VERIFICATION_REQUIRED =
  process.env.NEXT_PUBLIC_EMAIL_VERIFICATION_REQUIRED !== "false";

export function needsEmailVerification(user: Pick<User, "email" | "emailVerified"> | null | undefined): boolean {
  return EMAIL_VERIFICATION_REQUIRED && !!user && !!user.email && !user.emailVerified;
}

// Where the "Verify your email" page lives; `redirect` is where to go once verified
export function verifyEmailPath(redirect?: string | null, sent = false): string {
  const params = new URLSearchParams();
  if (redirect) params.set("redirect", redirect);
  if (sent) params.set("sent", "1");
  const query = params.toString();
  return `/auth/verify-email${query ? `?${query}` : ""}`;
}

// Sends the verification link; clicking it comes back to the verify page, which continues
export async function sendVerificationEmail(user: User, redirect?: string | null): Promise<void> {
  const settings =
    typeof window !== "undefined"
      ? { url: `${window.location.origin}${verifyEmailPath(redirect)}` }
      : undefined;
  try {
    await sendEmailVerification(user, settings);
  } catch (err: any) {
    // A continue URL on a domain Firebase doesn't allow yet: send the plain link instead
    if (err?.code === "auth/unauthorized-continue-uri" || err?.code === "auth/invalid-continue-uri") {
      await sendEmailVerification(user);
      return;
    }
    throw err;
  }
}
