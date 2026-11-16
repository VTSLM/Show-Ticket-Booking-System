"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import {
  auth,
  signInWithEmailAndPassword,
  signInWithPopup,
  googleProvider,
  sendPasswordResetEmail,
} from "@/lib/firebase";
import { authApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshProfile } = useAuth();
  const redirectTo = searchParams.get("redirect") || "/browse";

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const credential = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await credential.user.getIdToken(true);
      await authApi.verifyToken(idToken);
      await refreshProfile();
      toast.success("Welcome back!");
      router.push(redirectTo);
    } catch (err: any) {
      toast.error(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setLoading(true);

    try {
      const credential = await signInWithPopup(auth, googleProvider);
      const idToken = await credential.user.getIdToken();

      try {
        await authApi.verifyToken(idToken);
        toast.success("Logged in!");
        router.push(redirectTo);
      } catch {
        const name = encodeURIComponent(credential.user.displayName || "");
        const userEmail = encodeURIComponent(credential.user.email || "");
        const token = encodeURIComponent(idToken);

        router.push(
          `/auth/register?token=${token}&name=${name}&email=${userEmail}`
        );
      }
    } catch (err: any) {
      toast.error(err.message || "Google login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    const emailAddress = email.trim();

    if (!emailAddress) {
      toast.error("Enter your email address first.");
      return;
    }

    setLoading(true);

    try {
      await sendPasswordResetEmail(auth, emailAddress);
      toast.success(
        "If an account exists for that email, a password reset link has been sent."
      );
    } catch (err: any) {
      toast.error(
        err?.message || "Could not send the reset email. Check the email address and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-y-auto bg-[#050b14] px-4 py-8 text-white sm:px-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(21,36,56,0.65),_rgba(3,8,16,0.96)_55%,_rgba(2,6,12,1)_100%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.035),transparent_42%)]" />

      <section className="relative z-10 w-full max-w-[440px] rounded-3xl border border-white/10 bg-[#07111f]/90 p-6 shadow-[0_24px_70px_rgba(0,0,0,0.48)] backdrop-blur-md sm:p-8">
        <header className="mb-7">
          <h1 className="text-center text-3xl font-bold tracking-tight text-white sm:text-[2rem]">
            TicketFlow
          </h1>
          <h2 className="mt-7 text-3xl font-semibold tracking-tight text-white">
            Log in
          </h2>
        </header>

        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label
              htmlFor="email"
              className="mb-2 block text-sm font-medium text-white/85"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="w-full border-0 border-b border-white/25 bg-transparent px-0 py-2.5 text-base text-white placeholder:text-white/35 focus:border-blue-400 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-2 block text-sm font-medium text-white/85"
            >
              Password
            </label>
            <div className="flex items-center border-b border-white/25 focus-within:border-blue-400">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Enter your password"
                className="w-full border-0 bg-transparent px-0 py-2.5 text-base text-white placeholder:text-white/35 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="shrink-0 p-1 text-white/50 hover:text-white/90 transition-colors"
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
                    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                    <path d="M14.12 14.12a3 3 0 11-4.24-4.24" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                    <line x1="1" y1="1" x2="23" y2="23" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden="true">
                    <path d="M2 12C3.72 8.82 7.02 6.5 12 6.5C16.98 6.5 20.28 8.82 22 12C20.28 15.18 16.98 17.5 12 17.5C7.02 17.5 3.72 15.18 2 12Z" stroke="currentColor" strokeWidth="1.8"/>
                    <circle cx="12" cy="12" r="3.3" stroke="currentColor" strokeWidth="1.8"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="pt-0.5 text-right">
            <button
              type="button"
              onClick={handleForgotPassword}
              disabled={loading}
              className="text-sm font-medium text-white/75 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Forgot password?
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center rounded-xl bg-[#3478f6] px-4 py-3 text-base font-semibold text-white shadow-lg shadow-blue-900/25 transition hover:bg-[#2868df] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Logging in..." : "Log in"}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <span className="h-px flex-1 bg-white/10" />
          <span className="text-xs text-white/50">OR CONTINUE WITH</span>
          <span className="h-px flex-1 bg-white/10" />
        </div>

        <div className="flex justify-center">
          <button
            type="button"
            onClick={handleGoogle}
            disabled={loading}
            aria-label="Continue with Google"
            className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] transition hover:bg-white/[0.12] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-white/70">
          Don&apos;t have an account?{" "}
          <Link
            href="/auth/register"
            className="font-semibold text-blue-400 underline-offset-4 hover:text-blue-300 hover:underline"
          >
            Sign up
          </Link>
        </p>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
