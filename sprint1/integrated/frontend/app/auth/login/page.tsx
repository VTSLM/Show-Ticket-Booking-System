"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { auth, signInWithEmailAndPassword, signInWithPopup, googleProvider } from "@/lib/firebase";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await cred.user.getIdToken(true);
      await authApi.verifyToken(idToken);
      toast.success("Welcome back!");
      router.push("/browse");
    } catch (err: any) {
      toast.error(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setLoading(true);
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const idToken = await cred.user.getIdToken();
      try {
        await authApi.verifyToken(idToken);
        toast.success("Logged in!");
        router.push("/browse");
      } catch {
        const n = encodeURIComponent(cred.user.displayName || "");
        const em = encodeURIComponent(cred.user.email || "");
        const tk = encodeURIComponent(idToken);
        router.push(`/auth/register?token=${tk}&name=${n}&email=${em}`);
      }
    } catch (err: any) {
      toast.error(err.message || "Google login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-6 text-gray-900">Sign In to TicketFlow</h1>
        <form onSubmit={handleLogin} className="space-y-4">
          <input className="input" type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required />
          <input className="input" type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)} required />
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
        <div className="my-4 flex items-center gap-2">
          <div className="flex-1 border-t" /><span className="text-gray-400 text-sm">or</span><div className="flex-1 border-t" />
        </div>
        <button onClick={handleGoogle} disabled={loading}
          className="w-full border border-gray-300 rounded-lg py-2 flex items-center justify-center gap-2 hover:bg-gray-50 transition">
          <span>G</span> Continue with Google
        </button>
        <p className="text-center text-sm text-gray-500 mt-4">
          No account? <Link href="/auth/register" className="text-red-500 hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
}
