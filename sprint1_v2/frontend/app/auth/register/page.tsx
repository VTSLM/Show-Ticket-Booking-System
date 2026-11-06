"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  auth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
} from "@/lib/firebase";
import { authApi } from "@/lib/api";

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

  const localToday = new Date();
  localToday.setMinutes(localToday.getMinutes() - localToday.getTimezoneOffset());
  const maxBirthdate = localToday.toISOString().slice(0, 10);

  const handle = (key: string) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!prefillToken && form.password !== form.confirmPassword) {
      toast.error("Passwords do not match");
      return;
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
          // Preserve the existing behavior for an already-created Firebase account.
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-6">Create Account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            className="input"
            placeholder="Full Name"
            value={form.name}
            onChange={handle("name")}
            required
          />
          <input
            className="input"
            type="email"
            placeholder="Email"
            value={form.email}
            onChange={handle("email")}
            required
          />
          <input
            className="input"
            type="tel"
            placeholder="Phone (optional)"
            value={form.phone}
            onChange={handle("phone")}
          />
          <label className="block text-sm text-gray-600">
            Date of birth
            <input
              className="input mt-1"
              type="date"
              value={form.birthdate}
              onChange={handle("birthdate")}
              max={maxBirthdate}
              required
            />
          </label>

          {!prefillToken && (
            <>
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                placeholder="Password (min 6 chars)"
                value={form.password}
                onChange={handle("password")}
                required
                minLength={6}
              />
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                placeholder="Confirm password"
                value={form.confirmPassword}
                onChange={handle("confirmPassword")}
                required
                minLength={6}
              />
            </>
          )}

          <select className="input" value={form.role} onChange={handle("role")}>
            <option value="customer">Customer</option>
            <option value="manager">Manager (needs admin approval)</option>
            <option value="admin">Admin</option>
          </select>

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Registering..." : "Create Account"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-4">
          Already have an account?{" "}
          <Link href="/auth/login" className="text-red-500 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}