"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";

export default function AdminPage() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isAdmin) { router.push("/"); return; }
    if (!authLoading && isAdmin) {
      adminApi.pending().then(setPending).finally(() => setLoading(false));
    }
  }, [isAdmin, authLoading]);

  const handle = async (userId: string, action: "approve" | "reject") => {
    try {
      await adminApi.approve(userId, action);
      setPending(p => p.filter(u => u.id !== userId));
      toast.success(action === "approve" ? "User approved!" : "User rejected");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  if (authLoading || loading) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-3xl font-bold">Admin — Pending Approvals</h1>
        <Link href="/manager" className="btn-primary text-sm">
          Manage Shows, Events &amp; Venues
        </Link>
      </div>
      {pending.length === 0 ? (
        <div className="card text-center py-8 text-gray-400">No pending approvals.</div>
      ) : (
        <div className="space-y-4">
          {pending.map(u => (
            <div key={u.id} className="card flex justify-between items-center">
              <div>
                <p className="font-semibold">{u.name}</p>
                <p className="text-sm text-gray-500">{u.email} • {u.roles?.join(", ")}</p>
                <p className="text-xs text-gray-400">Registered {new Date(u.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handle(u.id, "approve")} className="btn-primary text-sm py-1 px-3">Approve</button>
                <button onClick={() => handle(u.id, "reject")}
                  className="bg-gray-200 text-gray-700 hover:bg-gray-300 text-sm py-1 px-3 rounded-lg">Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
