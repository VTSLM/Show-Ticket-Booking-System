"use client";
// src/app/login/page.tsx — Common login page for all stakeholders.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { auth, signInWithEmailAndPassword, signInWithPopup, googleProvider } from "@/lib/firebase";
import { verifyToken } from "@/lib/api";
import { FirebaseError } from "firebase/app";

interface LoginForm {
  email: string;
  password: string;
}

function firebaseErrorMessage(code: string, fallbackMessage?: string): string {
  switch (code) {
    case "auth/invalid-credential":
    case "auth/wrong-password":
    case "auth/user-not-found":
      return "Invalid email or password.";
    case "auth/too-many-requests":
      return "Too many failed attempts. Please try again later.";
    case "auth/user-disabled":
      return "This account has been disabled.";
    case "auth/operation-not-allowed":
      return "Sign-in method is not enabled in Firebase Console. Enable Email/Password in Authentication -> Sign-in method.";
    default:
      return fallbackMessage || `Login failed (${code || "unknown error"}).`;
  }
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>();

  // ---- helpers ----

  async function handlePostLogin(firebaseToken: string) {
    try {
      const { user } = await verifyToken(firebaseToken);
      if (user.status !== "active") {
        router.push("/pending-approval");
        return;
      }
      toast.success(`Welcome back, ${user.name}!`);
      router.push(user.redirect_to);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not load your profile.";
      // If the user has a Firebase account but is not in our DB, send them to register.
      if (msg.includes("not found")) {
        toast.error("No account found. Please register first.");
        router.push("/register");
      } else {
        toast.error(msg);
      }
    }
  }

  // ---- email/password login ----

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);
    try {
      const cred = await signInWithEmailAndPassword(auth, data.email, data.password);
      const token = await cred.user.getIdToken();
      await handlePostLogin(token);
    } catch (err: unknown) {
      console.error("Login error:", err);
      const code = err instanceof FirebaseError ? err.code : "";
      const msg = err instanceof Error ? err.message : "";
      toast.error(firebaseErrorMessage(code, msg));
    } finally {
      setLoading(false);
    }
  };

  // ---- Google login ----

  const handleGoogle = async () => {
    setGoogleLoading(true);
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const token = await cred.user.getIdToken();
      await handlePostLogin(token);
    } catch (err: unknown) {
      console.error("Google sign in error:", err);
      const code = err instanceof FirebaseError ? err.code : "";
      const msg = err instanceof Error ? err.message : "";
      if (code !== "auth/popup-closed-by-user") {
        toast.error(firebaseErrorMessage(code, msg));
      }
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      {/* Background decoration */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-brand-700/20 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-brand-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo / branding */}
        <div className="mb-8 text-center">
          <span className="text-4xl">🎭</span>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">ShowBook</h1>
          <p className="mt-1 text-sm text-gray-400">Sign in to book amazing experiences</p>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-2xl">
          <h2 className="mb-6 text-xl font-semibold text-white">Welcome back</h2>

          {/* Google OAuth */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleLoading || loading}
            className="mb-6 flex w-full items-center justify-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm font-medium text-gray-200 transition hover:bg-gray-700 disabled:opacity-50"
          >
            {googleLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            Continue with Google
          </button>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-xs text-gray-500">
              <span className="bg-gray-900 px-3">or sign in with email</span>
            </div>
          </div>

          {/* Email / password form */}
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-300">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500 focus:ring-0"
                {...register("email", {
                  required: "Email is required",
                  pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email" },
                })}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-gray-300">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500 focus:ring-0"
                {...register("password", { required: "Password is required" })}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || googleLoading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-50"
            >
              {loading && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}
              Sign in
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-400">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-brand-400 hover:text-brand-300 font-medium">
              Register
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
