"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { ReceivedTransfer, transfersApi } from "@/lib/transfersApi";
import ReceivedTicketList from "@/components/ReceivedTicketList";
import { auth } from "@/lib/firebase";
import { EMAIL_VERIFICATION_REQUIRED, sendVerificationEmail } from "@/lib/emailVerification";

export default function ReceivedTicketsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<ReceivedTransfer[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setItems(await transfersApi.received());
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load your tickets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/auth/login?redirect=%2Ftickets%2Freceived");
      return;
    }
    load();
  }, [authLoading, user, router, load]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <p className="mb-2 text-xs font-bold uppercase tracking-widest text-[var(--blue)]">From friends</p>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Received tickets</h1>
        <Link href="/tickets" className="btn-secondary text-sm">
          ← All tickets
        </Link>
      </div>

      {!EMAIL_VERIFICATION_REQUIRED && auth.currentUser && !auth.currentUser.emailVerified && (
        <div className="card mb-4 text-sm">
          <p>Verify your account email to receive invitations sent before you signed up.</p>
          <button className="btn-secondary mt-2" onClick={async () => {
            try {
              if (!auth.currentUser) return;
              await sendVerificationEmail(auth.currentUser, "/tickets/received");
              toast.success("Verification email sent. Open it, then refresh this page.");
            } catch { toast.error("Could not send the verification email."); }
          }}>Send verification email</button>
          <button className="btn-secondary mt-2 ml-2" onClick={async () => {
            try {
              if (!auth.currentUser) return;
              await auth.currentUser.reload();
              await auth.currentUser.getIdToken(true);
              await load();
            } catch { toast.error("Could not refresh verification status."); }
          }}>I verified my email</button>
        </div>
      )}

      {loading ? (
        <p className="text-[var(--muted)]">Loading…</p>
      ) : items.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-lg font-semibold text-white">No tickets yet</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            When someone sends you seats from their booking, they will show up here.
          </p>
        </div>
      ) : (
        <ReceivedTicketList items={items} onChanged={load} userEmail={user?.email} />
      )}
    </div>
  );
}
