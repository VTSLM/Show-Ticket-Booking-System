"use client";

// "Verify your email" (#208): where new and older email/password accounts land until they
// click the link in the verification email. Works with auth.currentUser directly, because the
// rest of the app treats an unverified account as logged out.
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { auth, onAuthStateChanged, signOut } from "@/lib/firebase";
import { friendlyFirebaseMessage } from "@/lib/errorMessages";
import { sendVerificationEmail } from "@/lib/emailVerification";

const RESEND_WAIT_SECONDS = 60;
const CHECK_EVERY_MS = 5000;

type Status = "checking" | "unverified" | "verified" | "signed-out";

// Only same-site paths, so the redirect can't send people elsewhere
function safeRedirect(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/browse";
}

function VerifyEmail() {
  const params = useSearchParams();
  const router = useRouter();
  const redirectTo = safeRedirect(params.get("redirect"));
  const [status, setStatus] = useState<Status>("checking");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(params.get("sent") === "1" ? RESEND_WAIT_SECONDS : 0);
  const finishing = useRef(false);

  // Verified: get a fresh login token (it now says the email is verified) and reload into the app
  const finish = useCallback(async () => {
    if (finishing.current || !auth.currentUser) return;
    finishing.current = true;
    setStatus("verified");
    try {
      await auth.currentUser.getIdToken(true);
    } catch {}
    toast.success("Email verified. Welcome to TicketFlow!");
    window.location.assign(redirectTo);
  }, [redirectTo]);

  const check = useCallback(async (): Promise<boolean> => {
    const user = auth.currentUser;
    if (!user) return false;
    try {
      await user.reload();
    } catch {}
    if (auth.currentUser?.emailVerified) {
      await finish();
      return true;
    }
    return false;
  }, [finish]);

  useEffect(() => {
    return onAuthStateChanged(auth, async (user) => {
      if (!user) {
        setStatus("signed-out");
        return;
      }
      setEmail(user.email || "");
      if (!(await check())) setStatus("unverified");
    });
  }, [check]);

  // Keep checking, so clicking the link in another tab or on the phone continues here
  useEffect(() => {
    if (status !== "unverified") return;
    const timer = setInterval(() => { check(); }, CHECK_EVERY_MS);
    return () => clearInterval(timer);
  }, [status, check]);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  const resend = async () => {
    if (!auth.currentUser || wait > 0) return;
    setBusy(true);
    try {
      await sendVerificationEmail(auth.currentUser, redirectTo);
      toast.success(`Verification email sent to ${auth.currentUser.email}`);
      setWait(RESEND_WAIT_SECONDS);
    } catch (err) {
      toast.error(friendlyFirebaseMessage(err, "Could not send the email. Please try again in a few minutes."));
    } finally {
      setBusy(false);
    }
  };

  const continueNow = async () => {
    setBusy(true);
    try {
      if (!(await check())) {
        toast.error("Your email isn't verified yet. Click the link in the email first.");
      }
    } finally {
      setBusy(false);
    }
  };

  const useAnotherAccount = async () => {
    await signOut(auth).catch(() => {});
    router.push(`/auth/login?redirect=${encodeURIComponent(redirectTo)}`);
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-y-auto bg-[#050b14] px-4 py-8 text-white sm:px-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(21,36,56,0.65),_rgba(3,8,16,0.96)_55%,_rgba(2,6,12,1)_100%)]" />
      <section
        data-testid="verify-email"
        className="relative z-10 w-full max-w-[460px] rounded-3xl border border-white/10 bg-[#07111f]/90 p-6 text-center shadow-[0_24px_70px_rgba(0,0,0,0.48)] backdrop-blur-md sm:p-8"
      >
        <h1 className="text-3xl font-bold tracking-tight">TicketFlow</h1>
        <p className="mt-6 text-5xl" aria-hidden="true">✉️</p>

        {status === "checking" && <p className="mt-4 text-white/70">Checking your account…</p>}

        {status === "verified" && (
          <p className="mt-4 text-lg font-semibold text-emerald-300">Email verified. Taking you in…</p>
        )}

        {status === "signed-out" && (
          <>
            <h2 className="mt-4 text-2xl font-semibold">Verify your email</h2>
            <p className="mt-2 text-sm text-white/70">
              If you have already clicked the link in the email, your account is verified. Log in to continue.
            </p>
            <Link
              href={`/auth/login?redirect=${encodeURIComponent(redirectTo)}`}
              className="mt-6 inline-block w-full rounded-xl bg-blue-500 px-4 py-3 font-semibold text-white transition hover:bg-blue-400"
            >
              Log in
            </Link>
          </>
        )}

        {status === "unverified" && (
          <>
            <h2 className="mt-4 text-2xl font-semibold">Verify your email</h2>
            <p className="mt-2 text-sm text-white/70">
              We sent a verification link to <span data-testid="verify-email-address" className="font-semibold text-white">{email}</span>.
              Click it to finish setting up your account. This page continues on its own once you have.
            </p>
            <p className="mt-2 text-xs text-white/50">Can&apos;t find it? Check your spam or promotions folder.</p>

            <div className="mt-6 space-y-3">
              <button
                type="button"
                onClick={continueNow}
                disabled={busy}
                className="w-full rounded-xl bg-blue-500 px-4 py-3 font-semibold text-white transition hover:bg-blue-400 disabled:opacity-60"
              >
                I&apos;ve verified, continue
              </button>
              <button
                type="button"
                onClick={resend}
                disabled={busy || wait > 0}
                className="w-full rounded-xl border border-white/15 px-4 py-3 font-semibold text-white/90 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {wait > 0 ? `Resend email (${wait}s)` : "Resend email"}
              </button>
              <button
                type="button"
                onClick={useAnotherAccount}
                className="w-full px-4 py-2 text-sm text-white/60 underline-offset-2 hover:text-white hover:underline"
              >
                Use a different account
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmail />
    </Suspense>
  );
}
