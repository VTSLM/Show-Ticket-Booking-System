"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { auth, createUserWithEmailAndPassword, signInWithEmailAndPassword } from "@/lib/firebase";
import { authApi } from "@/lib/api";

function RegisterForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [form, setForm] = useState({
    name: params.get("name") || "",
    email: params.get("email") || "",
    phone: "",
    password: "",
    role: "customer",
  });
  const [loading, setLoading] = useState(false);
  const prefillToken = params.get("token");

  const handle = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      let idToken = prefillToken || "";
      if (!idToken) {
        let cred;
        try {
          cred = await createUserWithEmailAndPassword(auth, form.email, form.password);
        } catch {
          cred = await signInWithEmailAndPassword(auth, form.email, form.password);
        }
        idToken = await cred.user.getIdToken();
      }
      const res = await authApi.register({ ...form, id_token: idToken }) as any;
      toast.success(res.message || "Registered!");
      if (form.role === "customer") {
        router.push("/browse");
      } else {
        router.push("/auth/login");
      }
    } catch (err: any) {
      toast.error(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-6">Create Account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input className="input" placeholder="Full Name" value={form.name}
            onChange={handle("name")} required />
          <input className="input" type="email" placeholder="Email" value={form.email}
            onChange={handle("email")} required />
          <input className="input" type="tel" placeholder="Phone (optional)" value={form.phone}
            onChange={handle("phone")} />
          {!prefillToken && (
            <input className="input" type="password" placeholder="Password (min 6 chars)" value={form.password}
              onChange={handle("password")} required minLength={6} />
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
          Already have an account? <Link href="/auth/login" className="text-red-500 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterForm /></Suspense>;
}
