"use client";

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

const ROLE_OPTIONS: {
  value: StakeholderRole;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    value: "customer",
    label: "Customer",
    description: "Browse shows and book tickets",
    icon: "🎟️",
  },
  {
    value: "manager",
    label: "Show Manager",
    description: "List and manage shows",
    icon: "🎬",
  },
  {
    value: "admin",
    label: "Administrator",
    description: "Full platform access",
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
      return "Email/Password provider is disabled in Firebase Console.";
    case "auth/unauthorized-domain":
      return "This domain is not authorized in Firebase.";
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
  } = useForm<RegisterForm>({
    defaultValues: { role: "customer" },
  });

  const selectedRole = watch("role");

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
        toast.success("Registration successful! Welcome aboard.");
        router.push("/login");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed.";
      toast.error(msg);
    }
  }

  const onSubmit = async (data: RegisterForm) => {
    setLoading(true);

    try {
      const cred = await createUserWithEmailAndPassword(
        auth,
        data.email,
        data.password
      );

      const token = await cred.user.getIdToken();

      await completeRegistration(
        token,
        data.name,
        data.email,
        data.phone,
        data.role
      );
    } catch (err: unknown) {
      console.error("Registration error:", err);

      const code = err instanceof FirebaseError ? err.code : "";
      const msg = err instanceof Error ? err.message : "";

      toast.error(firebaseErrorMessage(code, msg));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    const role = watch("role");
    const name = watch("name");

    if (!name?.trim()) {
      toast.error("Please enter your name before continuing with Google.");
      return;
    }

    setGoogleLoading(true);

    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const token = await cred.user.getIdToken();
      const email = cred.user.email ?? "";
      const displayName = name || cred.user.displayName || "User";

      await completeRegistration(
        token,
        displayName,
        email,
        watch("phone"),
        role
      );
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

  const inputClass =
    "w-full rounded-xl border border-[#243B59] bg-[#0B1B30] px-4 py-3 text-sm text-[#F5F9FF] placeholder-[#71849D] outline-none transition focus:border-[#1685FF] focus:ring-2 focus:ring-[#1685FF]/20";

  const labelClass = "mb-2 block text-sm font-medium text-[#DCE9F8]";

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#071426] px-4 py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-80 w-80 -translate-x-1/2 rounded-full bg-[#0066FF]/10 blur-[120px]" />
      </div>

      <div className="relative z-10 w-full max-w-xl">
        <div className="mb-7 text-center">
          <Link href="/login" className="inline-flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#0066FF] shadow-lg shadow-blue-950/40">
              <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-white">
                <path d="M5 4.5h14v15H5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                <path d="M9 4.5v15M15 4.5v15" stroke="currentColor" strokeWidth="1.5" />
                <path d="M5 9h14M5 15h14" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>

            <span className="text-3xl font-bold tracking-tight text-white">
              Ticket<span className="text-[#1685FF]">Flow</span>
            </span>
          </Link>

          <p className="mt-3 text-sm text-[#8FA5C0]">
            Your next experience starts here.
          </p>
        </div>

        <div className="rounded-2xl border border-[#1C3553] bg-[#0C1D33] p-6 shadow-2xl shadow-black/30 sm:p-8">
          <div className="mb-7">
            <h1 className="text-2xl font-bold text-white">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-[#91A5BF]">
              Join TicketFlow and discover your next live experience.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
            <div>
              <label htmlFor="name" className={labelClass}>Full name</label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                placeholder="Enter your full name"
                className={inputClass}
                {...register("name", {
                  required: "Name is required",
                  minLength: { value: 2, message: "Name is too short" },
                })}
              />
              {errors.name && <p className="mt-1.5 text-xs text-red-400">{errors.name.message}</p>}
            </div>

            <div>
              <label htmlFor="reg-email" className={labelClass}>Email address</label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className={inputClass}
                {...register("email", {
                  required: "Email is required",
                  pattern: { value: /^\S+@\S+\.\S+$/, message: "Enter a valid email" },
                })}
              />
              {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email.message}</p>}
            </div>

            <div>
              <label htmlFor="phone" className={labelClass}>
                Phone number <span className="font-normal text-[#71849D]">(optional)</span>
              </label>
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                placeholder="+91 98765 43210"
                className={inputClass}
                {...register("phone")}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="reg-password" className={labelClass}>Password</label>
                <input
                  id="reg-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 6 characters"
                  className={inputClass}
                  {...register("password", {
                    required: "Password is required",
                    minLength: { value: 6, message: "Password must be at least 6 characters" },
                  })}
                />
                {errors.password && <p className="mt-1.5 text-xs text-red-400">{errors.password.message}</p>}
              </div>

              <div>
                <label htmlFor="confirmPassword" className={labelClass}>Confirm password</label>
                <input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Re-enter password"
                  className={inputClass}
                  {...register("confirmPassword", {
                    required: "Please confirm your password",
                    validate: (v) => v === watch("password") || "Passwords do not match",
                  })}
                />
                {errors.confirmPassword && <p className="mt-1.5 text-xs text-red-400">{errors.confirmPassword.message}</p>}
              </div>
            </div>

            <div className="pt-2">
              <p className="mb-3 text-sm font-medium text-[#DCE9F8]">
                Choose your account type
              </p>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {ROLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setValue("role", opt.value, { shouldValidate: true })}
                    aria-pressed={selectedRole === opt.value}
                    className={`rounded-xl border p-3 text-left transition ${
                      selectedRole === opt.value
                        ? "border-[#1685FF] bg-[#0066FF]/10 ring-1 ring-[#1685FF]"
                        : "border-[#243B59] bg-[#0B1B30] hover:border-[#42658F]"
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-2xl">{opt.icon}</span>
                      <span className={`h-4 w-4 rounded-full border ${
                        selectedRole === opt.value
                          ? "border-[#1685FF] bg-[#1685FF] ring-2 ring-[#1685FF]/20"
                          : "border-[#526984]"
                      }`} />
                    </div>
                    <span className="block text-sm font-semibold text-white">{opt.label}</span>
                    <span className="mt-1 block text-xs leading-relaxed text-[#8FA5C0]">{opt.description}</span>
                  </button>
                ))}
              </div>

              {selectedRole !== "customer" && (
                <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                  <p className="text-xs leading-relaxed text-amber-200">
                    <strong>{ROLE_OPTIONS.find((r) => r.value === selectedRole)?.label}</strong>{" "}
                    accounts require admin approval before platform access.
                    You&apos;ll receive an email once your account is activated.
                  </p>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || googleLoading}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#0066FF] px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-[#1685FF] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
              {loading ? "Creating account..." : "Create account"}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#243B59]" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-[#0C1D33] px-3 text-xs text-[#71849D]">
                OR CONTINUE WITH
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleLoading || loading}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#29415F] bg-[#10243D] px-4 py-3 text-sm font-medium text-[#E5EFFB] transition hover:border-[#42658F] hover:bg-[#142B48] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {googleLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
            )}
            {googleLoading ? "Please wait..." : "Sign up with Google"}
          </button>

          <p className="mt-7 text-center text-sm text-[#8FA5C0]">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold text-[#1685FF] transition hover:text-[#8EDBFF]">
              Sign in
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-[#60758F]">
          © {new Date().getFullYear()} TicketFlow. All rights reserved.
        </p>
      </div>
    </main>
  );
}