"use client";
// src/app/register/page.tsx — Registration page for all stakeholder types.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import {
  auth,
  createUserWithEmailAndPassword,
  signInWithPopup,
  googleProvider,
} from "@/lib/firebase";
import { registerUser, StakeholderRole } from "@/lib/api";
import { FirebaseError } from "firebase/app";

interface RegisterForm {
  name: string;
  email: string;
  phone: string;
  password: string;
  confirmPassword: string;
  role: StakeholderRole;
}

const ROLE_OPTIONS: { value: StakeholderRole; label: string; description: string; icon: string }[] =
  [
    {
      value: "customer",
      label: "Customer",
      description: "Browse shows and book tickets",
      icon: "🎟️",
    },
    {
      value: "manager",
      label: "Show Manager",
      description: "List and manage shows (requires admin approval)",
      icon: "🎬",
    },
    {
      value: "admin",
      label: "Administrator",
      description: "Full platform access (requires admin approval)",
      icon: "🛡️",
    },
  ];

function firebaseErrorMessage(code: string, fallbackMessage?: string): string {
  switch (code) {
    case "auth/email-already-in-use":
      return "An account with this email already exists. Please log in.";
    case "auth/weak-password":
      return "Password must be at least 6 characters.";
    case "auth/invalid-email":
      return "Invalid email address.";
    case "auth/operation-not-allowed":
      return "Email/Password provider is disabled in Firebase Console! Enable it under Authentication -> Sign-in method.";
    case "auth/unauthorized-domain":
      return "This domain is not authorized in Firebase. Add 'localhost' in Firebase Authentication -> Settings -> Authorized domains.";
    case "auth/network-request-failed":
      return "Network error. Please check your internet connection.";
    default:
      return fallbackMessage || `Registration failed (${code || "unknown error"}).`;
  }
}

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const router = useRouter();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RegisterForm>({ defaultValues: { role: "customer" } });

  const selectedRole = watch("role");

  // ---- helpers ----

  async function completeRegistration(
    firebaseToken: string,
    name: string,
    email: string,
    phone: string,
    role: StakeholderRole
  ) {
    try {
      const result = await registerUser({
        firebase_token: firebaseToken,
        name,
        email,
        phone: phone || undefined,
        requested_role: role,
      });

      if (result.status === "pending_approval") {
        toast.success("Registration submitted! Awaiting admin approval.");
        router.push("/pending-approval");
      } else {
        toast.success("Registration successful! Welcome aboard 🎉");
        router.push("/login");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed.";
      toast.error(msg);
    }
  }

  // ---- email / password ----

  const onSubmit = async (data: RegisterForm) => {
    setLoading(true);
    try {
      const cred = await createUserWithEmailAndPassword(auth, data.email, data.password);
      const token = await cred.user.getIdToken();
      await completeRegistration(token, data.name, data.email, data.phone, data.role);
    } catch (err: unknown) {
      console.error("Registration error:", err);
      const code = err instanceof FirebaseError ? err.code : "";
      const msg = err instanceof Error ? err.message : "";
      toast.error(firebaseErrorMessage(code, msg));
    } finally {
      setLoading(false);
    }
  };

  // ---- Google ----

  const handleGoogle = async () => {
    const role = watch("role");
    const name = watch("name");
    if (!name.trim()) {
      toast.error("Please enter your name before continuing with Google.");
      return;
    }
    setGoogleLoading(true);
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const token = await cred.user.getIdToken();
      const email = cred.user.email ?? "";
      const displayName = name || cred.user.displayName || "User";
      await completeRegistration(token, displayName, email, watch("phone"), role);
    } catch (err: unknown) {
      console.error("Google sign up error:", err);
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
    <main className="flex min-h-screen items-center justify-center bg-gray-950 px-4 py-12">
      {/* Background decoration */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-brand-700/20 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-brand-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-lg">
        {/* Logo */}
        <div className="mb-8 text-center">
          <span className="text-4xl">🎭</span>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">ShowBook</h1>
          <p className="mt-1 text-sm text-gray-400">Create your account</p>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-2xl">
          <h2 className="mb-6 text-xl font-semibold text-white">Join ShowBook</h2>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
            {/* Name */}
            <div>
              <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-gray-300">
                Full name
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                placeholder="John Doe"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500"
                {...register("name", { required: "Name is required", minLength: { value: 2, message: "Name is too short" } })}
              />
              {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>}
            </div>

            {/* Email */}
            <div>
              <label htmlFor="reg-email" className="mb-1.5 block text-sm font-medium text-gray-300">
                Email address
              </label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500"
                {...register("email", {
                  required: "Email is required",
                  pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email" },
                })}
              />
              {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
            </div>

            {/* Phone (optional) */}
            <div>
              <label htmlFor="phone" className="mb-1.5 block text-sm font-medium text-gray-300">
                Phone{" "}
                <span className="text-gray-500 font-normal">(optional)</span>
              </label>
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                placeholder="+91 98765 43210"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500"
                {...register("phone")}
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="reg-password" className="mb-1.5 block text-sm font-medium text-gray-300">
                Password
              </label>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                placeholder="At least 6 characters"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500"
                {...register("password", {
                  required: "Password is required",
                  minLength: { value: 6, message: "Password must be at least 6 characters" },
                })}
              />
              {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirmPassword" className="mb-1.5 block text-sm font-medium text-gray-300">
                Confirm password
              </label>
              <input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                placeholder="••••••••"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder-gray-500 transition focus:border-brand-500"
                {...register("confirmPassword", {
                  required: "Please confirm your password",
                  validate: (v) => v === watch("password") || "Passwords do not match",
                })}
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-red-400">{errors.confirmPassword.message}</p>
              )}
            </div>

            {/* Role selection */}
            <div>
              <p className="mb-2 text-sm font-medium text-gray-300">I am a…</p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {ROLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setValue("role", opt.value)}
                    className={`flex flex-col items-center rounded-xl border p-3 text-center transition ${
                      selectedRole === opt.value
                        ? "border-brand-500 bg-brand-950/50 ring-1 ring-brand-500"
                        : "border-gray-700 bg-gray-800 hover:border-gray-600"
                    }`}
                  >
                    <span className="text-2xl">{opt.icon}</span>
                    <span className="mt-1 text-sm font-medium text-white">{opt.label}</span>
                    <span className="mt-0.5 text-xs text-gray-400">{opt.description}</span>
                  </button>
                ))}
              </div>

              {/* Approval notice for non-customer roles */}
              {selectedRole !== "customer" && (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-700/50 bg-amber-900/20 px-3 py-2.5">
                  <span className="mt-0.5 text-amber-400">⚠️</span>
                  <p className="text-xs text-amber-300">
                    <strong>{ROLE_OPTIONS.find((r) => r.value === selectedRole)?.label}</strong>{" "}
                    accounts require admin approval before you can access the platform.
                    You&apos;ll receive an email once your account is activated.
                  </p>
                </div>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || googleLoading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-50"
            >
              {loading && (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}
              Create account
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-xs text-gray-500">
              <span className="bg-gray-900 px-3">or continue with</span>
            </div>
          </div>

          {/* Google (for non-customer, they still pick their role first) */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleLoading || loading}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm font-medium text-gray-200 transition hover:bg-gray-700 disabled:opacity-50"
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
            Sign up with Google
          </button>

          <p className="mt-6 text-center text-sm text-gray-400">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand-400 hover:text-brand-300">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
