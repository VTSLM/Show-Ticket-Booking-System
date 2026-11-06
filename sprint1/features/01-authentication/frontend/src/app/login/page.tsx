"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import {
  auth,
  signInWithEmailAndPassword,
  signInWithPopup,
  googleProvider,
} from "@/lib/firebase";
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
      const msg =
        err instanceof Error ? err.message : "Could not load your profile.";

      if (msg.includes("not found")) {
        toast.error("No account found. Please register first.");
        router.push("/register");
      } else {
        toast.error(msg);
      }
    }
  }

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);

    try {
      const cred = await signInWithEmailAndPassword(
        auth,
        data.email,
        data.password
      );

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
    <main className="flex min-h-screen items-center justify-center bg-[#071426] px-4 py-10">

      <div className="w-full max-w-md">

        {/* TicketFlow Branding */}
        <div className="mb-9 text-center">

          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0066FF] shadow-lg shadow-blue-600/20">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              className="h-8 w-8 text-white"
            >
              <path
                d="M4 7.5A2.5 2.5 0 0 1 6.5 5h11A2.5 2.5 0 0 1 20 7.5V9a2 2 0 0 0 0 4v3.5a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5V13a2 2 0 0 0 0-4V7.5Z"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="M14 8v2M14 14v2"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </div>

          <h1 className="text-4xl font-bold tracking-tight text-white">
            Ticket<span className="text-[#1685FF]">Flow</span>
          </h1>

          <p className="mt-2 text-sm text-[#91A7C4]">
            Your next experience starts here.
          </p>

        </div>

        {/* Login Card */}
        <div className="rounded-2xl border border-[#183456] bg-[#0D2038] p-7 shadow-2xl shadow-black/20 sm:p-9">

          <div className="mb-7">
            <h2 className="text-2xl font-semibold text-white">
              Welcome back
            </h2>

            <p className="mt-2 text-sm text-[#91A7C4]">
              Sign in to continue to your account.
            </p>
          </div>

          {/* Google Login */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleLoading || loading}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#294361] bg-[#102945] px-4 py-3 text-sm font-medium text-white transition hover:border-[#1685FF] hover:bg-[#153455] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {googleLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <svg className="h-5 w-5" viewBox="0 0 24 24">
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
            )}

            Continue with Google
          </button>

          {/* Divider */}
          <div className="my-7 flex items-center gap-4">
            <div className="h-px flex-1 bg-[#294361]" />
            <span className="text-xs text-[#7189A7]">
              OR CONTINUE WITH EMAIL
            </span>
            <div className="h-px flex-1 bg-[#294361]" />
          </div>

          {/* Email and Password Form */}
          <form
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            className="space-y-5"
          >

            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-sm font-medium text-[#D6E4F5]"
              >
                Email address
              </label>

              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full rounded-xl border border-[#294361] bg-[#091A2D] px-4 py-3 text-sm text-white outline-none transition placeholder:text-[#617A99] focus:border-[#1685FF] focus:ring-2 focus:ring-[#1685FF]/20"
                {...register("email", {
                  required: "Email is required",
                  pattern: {
                    value: /^\S+@\S+\.\S+$/,
                    message: "Enter a valid email",
                  },
                })}
              />

              {errors.email && (
                <p className="mt-2 text-xs text-red-400">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-medium text-[#D6E4F5]"
              >
                Password
              </label>

              <input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                className="w-full rounded-xl border border-[#294361] bg-[#091A2D] px-4 py-3 text-sm text-white outline-none transition placeholder:text-[#617A99] focus:border-[#1685FF] focus:ring-2 focus:ring-[#1685FF]/20"
                {...register("password", {
                  required: "Password is required",
                })}
              />

              {errors.password && (
                <p className="mt-2 text-xs text-red-400">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Sign In Button */}
            <button
              type="submit"
              disabled={loading || googleLoading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#0066FF] px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-[#1685FF] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}

              {loading ? "Signing in..." : "Sign in"}
            </button>

          </form>

          {/* Registration Link */}
          <p className="mt-8 text-center text-sm text-[#91A7C4]">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="font-semibold text-[#1685FF] transition hover:text-[#70B8FF]"
            >
              Create an account
            </Link>
          </p>

        </div>

        <p className="mt-7 text-center text-xs text-[#617A99]">
          © {new Date().getFullYear()} TicketFlow. All rights reserved.
        </p>

      </div>
    </main>
  );
}