"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  auth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
} from "@/lib/firebase";
import { authApi } from "@/lib/api";

function PasswordVisibilityIcon({ visible }: { visible: boolean }) {
  return visible ? (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9.9 5.2A10.7 10.7 0 0 1 12 5c5 0 8.3 3.2 10 7-0.7 1.5-1.6 2.8-2.8 3.8M6.2 6.2C4.3 7.4 2.9 9.1 2 12c1.7 3.8 5 7 10 7 1.3 0 2.5-.2 3.5-.6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ) : (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M2 12s3.3-7 10-7 10 7 10 7-3.3 7-10 7-10-7-10-7Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle
        cx="12"
        cy="12"
        r="3"
        stroke="currentColor"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function RegisterForm() {
  const params = useSearchParams();
  const router = useRouter();
  const prefillToken = params.get("token");

  const [form, setForm] = useState({
    name: params.get("name") || "",
    email: params.get("email") || "",
    phone: "",
    birthdate: "",
    password: "",
    confirmPassword: "",
    role: "customer",
  });
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const localToday = new Date();
  localToday.setMinutes(
    localToday.getMinutes() - localToday.getTimezoneOffset()
  );
  const maxBirthdate = localToday.toISOString().slice(0, 10);

  const handle =
    (key: keyof typeof form) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm((current) => ({ ...current, [key]: event.target.value }));
    };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!prefillToken) {
      const failedRequirements: string[] = [];

      if (form.password.length < 8) {
        failedRequirements.push("at least 8 characters");
      }
      if (!/[A-Z]/.test(form.password)) {
        failedRequirements.push("an uppercase letter");
      }
      if (!/[a-z]/.test(form.password)) {
        failedRequirements.push("a lowercase letter");
      }
      if (!/\d/.test(form.password)) {
        failedRequirements.push("a digit (0–9)");
      }
      if (!/[^A-Za-z0-9\s]/.test(form.password)) {
        failedRequirements.push("a symbol");
      }
      if (/\s/.test(form.password)) {
        failedRequirements.push("no spaces");
      }

      if (failedRequirements.length > 0) {
        toast.error(
          `Weak password. It needs ${failedRequirements.join(", ")}.`,
          { duration: 5000 }
        );
        return;
      }

      if (form.password !== form.confirmPassword) {
        toast.error("Passwords do not match");
        return;
      }
    }

    setLoading(true);

    try {
      let idToken = prefillToken || "";

      if (!idToken) {
        try {
          const credential = await createUserWithEmailAndPassword(
            auth,
            form.email,
            form.password
          );
          idToken = await credential.user.getIdToken();
        } catch {
          // Keep the existing behavior for an already-created Firebase account.
          const credential = await signInWithEmailAndPassword(
            auth,
            form.email,
            form.password
          );
          idToken = await credential.user.getIdToken();
        }
      }

      // Never send either password field to the application backend.
      const { password, confirmPassword, ...registrationData } = form;
      const response = (await authApi.register({
        ...registrationData,
        id_token: idToken,
      })) as { message?: string };

      toast.success(response.message || "Registered!");
      router.push(form.role === "customer" ? "/browse" : "/auth/login");
    } catch (error: any) {
      toast.error(error.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full rounded-xl border border-white/15 bg-[#091522]/90 px-4 py-3 text-base text-white outline-none transition placeholder:text-white/35 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20";

  const labelClass = "mb-2 block text-sm font-medium text-white/85";

  return (
    <main className="relative min-h-screen overflow-y-auto bg-[#050b14] px-4 py-6 text-white sm:px-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(21,36,56,0.75),_rgba(3,8,16,0.96)_46%,_rgba(2,6,12,1)_100%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),transparent_40%)]" />

      <div className="relative z-10 mx-auto flex min-h-[calc(100vh-3rem)] max-w-3xl items-center justify-center">
        <section className="w-full rounded-[28px] border border-white/10 bg-[#040b16]/85 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.6)] backdrop-blur-md sm:p-8 lg:p-9">
          <header className="mb-6">
            <h1 className="text-center text-3xl font-black tracking-tight sm:text-4xl">
              TicketFlow
            </h1>
            <h2 className="mt-6 text-3xl font-black tracking-tight">
              Create account
            </h2>
            <p className="mt-2 text-sm text-white/60">
              Enter your details to get started.
            </p>
          </header>

          {prefillToken && (
            <p className="mb-5 rounded-xl border border-blue-400/20 bg-blue-400/10 px-4 py-3 text-sm text-blue-100">
              Your name and email were filled in from Google. Complete the
              remaining details to finish registration.
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="name" className={labelClass}>
                  Full name
                </label>
                <input
                  id="name"
                  className={inputClass}
                  type="text"
                  autoComplete="name"
                  placeholder="Your full name"
                  value={form.name}
                  onChange={handle("name")}
                  required
                />
              </div>

              <div>
                <label htmlFor="email" className={labelClass}>
                  Email address
                </label>
                <input
                  id="email"
                  className={inputClass}
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={handle("email")}
                  required
                />
              </div>

              <div>
                <label htmlFor="phone" className={labelClass}>
                  Phone <span className="text-white/45">(optional)</span>
                </label>
                <input
                  id="phone"
                  className={inputClass}
                  type="tel"
                  autoComplete="tel"
                  placeholder="Your phone number"
                  value={form.phone}
                  onChange={handle("phone")}
                />
              </div>

              <div>
                <label htmlFor="birthdate" className={labelClass}>
                  Date of birth
                </label>
                <input
                  id="birthdate"
                  className={`${inputClass} [color-scheme:dark]`}
                  type="date"
                  value={form.birthdate}
                  onChange={handle("birthdate")}
                  max={maxBirthdate}
                  required
                />
              </div>

              {!prefillToken && (
                <>
                  <div>
                    <label htmlFor="password" className={labelClass}>
                      Password
                    </label>
                    <div className="relative">
                      <input
                        id="password"
                        className={`${inputClass} pr-12`}
                        type={showPassword ? "text" : "password"}
                        autoComplete="new-password"
                        placeholder="Min password length: 8 characters"
                        value={form.password}
                        onChange={handle("password")}
                        required
                        minLength={8}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((visible) => !visible)}
                        className="absolute inset-y-0 right-0 flex items-center px-4 text-white/65 transition hover:text-white"
                        aria-label={
                          showPassword ? "Hide password" : "Show password"
                        }
                        aria-pressed={showPassword}
                      >
                        <PasswordVisibilityIcon visible={showPassword} />
                      </button>
                    </div>
                  </div>

                  <div>
                    <label htmlFor="confirmPassword" className={labelClass}>
                      Confirm password
                    </label>
                    <div className="relative">
                      <input
                        id="confirmPassword"
                        className={`${inputClass} pr-12`}
                        type={showConfirmPassword ? "text" : "password"}
                        autoComplete="new-password"
                        placeholder="Enter password again"
                        value={form.confirmPassword}
                        onChange={handle("confirmPassword")}
                        required
                        minLength={8}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowConfirmPassword((visible) => !visible)
                        }
                        className="absolute inset-y-0 right-0 flex items-center px-4 text-white/65 transition hover:text-white"
                        aria-label={
                          showConfirmPassword
                            ? "Hide confirm password"
                            : "Show confirm password"
                        }
                        aria-pressed={showConfirmPassword}
                      >
                        <PasswordVisibilityIcon
                          visible={showConfirmPassword}
                        />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div>
              <label htmlFor="role" className={labelClass}>
                Account type
              </label>
              <select
                id="role"
                className={`${inputClass} [color-scheme:dark]`}
                value={form.role}
                onChange={handle("role")}
              >
                <option value="customer">Customer</option>
                <option value="manager">Manager (needs admin approval)</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center rounded-xl bg-[#3b82f6] px-4 py-4 text-lg font-semibold text-white shadow-[0_16px_34px_rgba(59,130,246,0.3)] transition hover:bg-[#2f73ff] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading ? "Creating your account..." : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-white/70">
            Already have an account?{" "}
            <Link
              href="/auth/login"
              className="font-semibold text-blue-400 underline-offset-4 hover:text-blue-300 hover:underline"
            >
              Log in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[#050b14] text-white">
          <p className="text-white/70">Loading registration form...</p>
        </main>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}