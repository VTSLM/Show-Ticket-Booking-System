"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

type Transfer = { id: string; event_title: string; sender_name: string; recipient_name: string;
  status: string; seats: number; created_at: string };
type Result = { total: number; page: number; transfers: Transfer[] };

export default function AdminTransfers() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (authLoading) return;
    if (!isAdmin) { router.push("/"); return; }
    let active = true;
    setResult(null); setError("");
    api.get<Result>(`/api/transfers/admin?page=${page}&page_size=25`)
      .then(data => { if (active) setResult(data); })
      .catch(() => { if (active) setError("Could not load transfers."); });
    return () => { active = false; };
  }, [authLoading, isAdmin, page, router]);
  return <main className="max-w-5xl mx-auto px-4 py-8">
    <Link href="/admin" className="text-blue-400">← Admin</Link>
    <h1 className="text-3xl font-bold my-6">Ticket transfers</h1>
    {error && <p role="alert">{error}</p>}
    {!result && !error && <p>Loading transfers…</p>}
    {result && <>
      <p className="text-slate-400 mb-4">{result.total} transfers</p>
      {result.transfers.length === 0 ? <p>No transfers found.</p> : <div className="space-y-3">
        {result.transfers.map(t => <div key={t.id} className="card">
          <p className="font-semibold">{t.event_title}</p>
          <p>{t.sender_name} → {t.recipient_name}</p>
          <p className="text-sm text-slate-400">{t.seats} seats · {t.status} · {new Date(t.created_at).toLocaleString()}</p>
        </div>)}
      </div>}
      <div className="flex gap-4 mt-6">
        <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button>
        <span>Page {page}</span>
        <button className="btn-secondary" disabled={page * 25 >= result.total} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </>}
  </main>;
}
