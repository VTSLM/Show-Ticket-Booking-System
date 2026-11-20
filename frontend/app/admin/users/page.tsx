"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { adminUsersApi, AdminAuditEntry, AdminUser, AdminUserStatus } from "@/lib/api";

const PAGE_SIZE = 25;

type PendingAction =
  | { kind: "role"; user: AdminUser; role: "manager" | "admin"; action: "add" | "remove" }
  | { kind: "status"; user: AdminUser; status: "active" | "blocked" };

const STATUS_STYLE: Record<AdminUserStatus, string> = {
  active: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30",
  inactive: "bg-amber-500/20 text-amber-300 border border-amber-500/30",
  blocked: "bg-red-500/20 text-red-300 border border-red-500/30",
};
const STATUS_LABEL: Record<AdminUserStatus, string> = {
  active: "Active",
  inactive: "Pending approval",
  blocked: "Blocked",
};

function describe(action: PendingAction): { title: string; effect: string; confirm: string; danger: boolean } {
  const name = action.user.name;
  if (action.kind === "status") {
    return action.status === "blocked"
      ? {
          title: `Block ${name}?`,
          effect: "They are signed out and every request they make is refused until an admin unblocks them.",
          confirm: "Block user",
          danger: true,
        }
      : {
          title: `Unblock ${name}?`,
          effect: "They can sign in and use TicketFlow again with their current roles.",
          confirm: "Unblock user",
          danger: false,
        };
  }
  const verb = action.action === "add" ? "Give" : "Remove";
  const effect =
    action.role === "admin"
      ? action.action === "add"
        ? "Admins can manage every user, venue, organizer and refund."
        : "They lose access to all admin pages."
      : action.action === "add"
      ? "Managers can create events and shows for their organisation."
      : "They lose access to the manager dashboard.";
  return {
    title: `${verb} the ${action.role} role ${action.action === "add" ? "to" : "from"} ${name}?`,
    effect,
    confirm: `${verb} ${action.role} role`,
    danger: action.action === "remove" || action.role === "admin",
  };
}

const AUDIT_LABEL: Record<AdminAuditEntry["action"], (d: Record<string, string>) => string> = {
  role_added: (d) => `Added the ${d.role} role`,
  role_removed: (d) => `Removed the ${d.role} role`,
  status_changed: (d) => `Status ${d.from} → ${d.to}`,
  manager_approved: () => "Approved manager sign-up",
  manager_rejected: () => "Rejected manager sign-up",
};

export default function AdminUsersPage() {
  const { isAdmin, profile, loading: authLoading } = useAuth();
  const router = useRouter();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const [selected, setSelected] = useState<(AdminUser & { history: AdminAuditEntry[] }) | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminUsersApi.list({ q: query || undefined, role, status, page, page_size: PAGE_SIZE });
      setUsers(res.users);
      setTotal(res.total);
    } catch (e: any) {
      toast.error(e.message || "Could not load users");
    } finally {
      setLoading(false);
    }
  }, [query, role, status, page]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAdmin) {
      router.push("/");
      return;
    }
    load();
  }, [authLoading, isAdmin, load, router]);

  const openUser = async (user: AdminUser) => {
    try {
      setSelected(await adminUsersApi.get(user.id));
    } catch (e: any) {
      toast.error(e.message || "Could not load this user");
    }
  };

  const confirmAction = async () => {
    if (!pending) return;
    if (reason.trim().length < 3) {
      toast.error("Please give a reason (at least 3 characters).");
      return;
    }
    setSaving(true);
    try {
      if (pending.kind === "role") {
        await adminUsersApi.changeRole(pending.user.id, pending.role, pending.action, reason.trim());
      } else {
        await adminUsersApi.changeStatus(pending.user.id, pending.status, reason.trim());
      }
      toast.success("Saved");
      const userId = pending.user.id;
      setPending(null);
      setReason("");
      await load();
      setSelected(await adminUsersApi.get(userId));
    } catch (e: any) {
      toast.error(e.message || "Could not save the change");
    } finally {
      setSaving(false);
    }
  };

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isSelf = (u: AdminUser) => profile?.id === u.id;

  if (authLoading) {
    return <main className="min-h-screen bg-[#070c18] text-gray-400 flex items-center justify-center">Loading…</main>;
  }

  return (
    <main className="min-h-screen bg-[#070c18] text-white px-4 py-8 sm:px-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Users</h1>
            <p className="text-sm text-gray-400 mt-1">Search accounts, change roles, and block or unblock users.</p>
          </div>
          <p className="text-xs text-gray-400">
            {total} {total === 1 ? "user" : "users"}
          </p>
        </header>

        <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-4 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
          <form
            className="flex gap-2 w-full md:w-96"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setQuery(search.trim());
            }}
          >
            <label htmlFor="user-search" className="sr-only">Search by name or email</label>
            <input
              id="user-search"
              value={search}
              maxLength={100}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or email"
              className="w-full bg-[#050b14] border border-white/10 rounded-xl px-4 py-2 text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <button type="submit" className="px-4 py-2 text-sm font-semibold rounded-xl bg-blue-600 hover:bg-blue-500">
              Search
            </button>
          </form>
          <div className="flex gap-3">
            <label className="sr-only" htmlFor="role-filter">Role</label>
            <select
              id="role-filter"
              value={role}
              onChange={(e) => { setPage(1); setRole(e.target.value); }}
              className="bg-[#050b14] border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">All roles</option>
              <option value="customer">Customer</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
            <label className="sr-only" htmlFor="status-filter">Status</label>
            <select
              id="status-filter"
              value={status}
              onChange={(e) => { setPage(1); setStatus(e.target.value); }}
              className="bg-[#050b14] border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Pending approval</option>
              <option value="blocked">Blocked</option>
            </select>
          </div>
        </div>

        {loading ? (
          <p className="text-center text-sm text-gray-400 py-12">Loading users…</p>
        ) : users.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-[#0b1426] p-12 text-center text-sm text-gray-400">
            No users match these filters.
          </div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-[#0b1426] overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="border-b border-white/10 bg-[#080f1e] text-xs uppercase tracking-wider text-gray-400">
                <tr>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Roles</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Joined</th>
                  <th className="py-3 px-4 text-right"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-white/[0.02]">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">
                        {u.name} {isSelf(u) && <span className="ml-1 text-xs text-blue-300">(you)</span>}
                      </div>
                      <div className="text-xs text-gray-500">{u.email}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((r) => (
                          <span key={r} className="text-xs px-2 py-0.5 rounded bg-white/5 border border-white/10 capitalize">{r}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATUS_STYLE[u.status]}`}>
                        {STATUS_LABEL[u.status]}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-400">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => openUser(u)}
                        className="px-3 py-1 text-xs font-medium rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30"
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <nav className="flex items-center justify-between text-sm text-gray-400" aria-label="Pages">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 rounded-lg border border-white/10 disabled:opacity-40">
              ← Previous
            </button>
            <span>Page {page} of {pages}</span>
            <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 rounded-lg border border-white/10 disabled:opacity-40">
              Next →
            </button>
          </nav>
        )}
      </div>

      {selected && (
        <div className="fixed inset-0 z-40 bg-black/60 flex justify-end" onClick={() => setSelected(null)}>
          <aside
            role="dialog"
            aria-modal="true"
            aria-label={`Manage ${selected.name}`}
            className="w-full max-w-md h-full overflow-y-auto bg-[#0b1426] border-l border-white/10 p-6 space-y-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold">{selected.name}</h2>
                <p className="text-sm text-gray-400">{selected.email}</p>
                {selected.phone && <p className="text-sm text-gray-500">{selected.phone}</p>}
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white" aria-label="Close">✕</button>
            </div>

            {isSelf(selected) ? (
              <p className="text-sm text-gray-400 rounded-xl border border-white/10 p-3">
                You can&apos;t change your own roles or status. Ask another admin.
              </p>
            ) : (
              <>
                <section className="space-y-2">
                  <h3 className="text-xs uppercase tracking-wider text-gray-400">Roles</h3>
                  {(["manager", "admin"] as const).map((r) => {
                    const has = selected.roles.includes(r);
                    return (
                      <div key={r} className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2">
                        <span className="capitalize">{r}</span>
                        <button
                          onClick={() => setPending({ kind: "role", user: selected, role: r, action: has ? "remove" : "add" })}
                          className={`px-3 py-1 text-xs rounded-lg border ${has ? "border-red-500/30 text-red-300 hover:bg-red-600/20" : "border-emerald-500/30 text-emerald-300 hover:bg-emerald-600/20"}`}
                        >
                          {has ? "Remove" : "Give"}
                        </button>
                      </div>
                    );
                  })}
                </section>

                <section className="space-y-2">
                  <h3 className="text-xs uppercase tracking-wider text-gray-400">Account</h3>
                  <div className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATUS_STYLE[selected.status]}`}>
                      {STATUS_LABEL[selected.status]}
                    </span>
                    {selected.status === "blocked" ? (
                      <button
                        onClick={() => setPending({ kind: "status", user: selected, status: "active" })}
                        className="px-3 py-1 text-xs rounded-lg border border-emerald-500/30 text-emerald-300 hover:bg-emerald-600/20"
                      >
                        Unblock
                      </button>
                    ) : (
                      <button
                        onClick={() => setPending({ kind: "status", user: selected, status: "blocked" })}
                        className="px-3 py-1 text-xs rounded-lg border border-red-500/30 text-red-300 hover:bg-red-600/20"
                      >
                        Block
                      </button>
                    )}
                  </div>
                  {selected.status === "inactive" && (
                    <p className="text-xs text-gray-500">Pending manager sign-ups are approved on the Admin page.</p>
                  )}
                </section>
              </>
            )}

            <section className="space-y-2">
              <h3 className="text-xs uppercase tracking-wider text-gray-400">History</h3>
              {selected.history.length === 0 ? (
                <p className="text-sm text-gray-500">No admin changes yet.</p>
              ) : (
                <ol className="space-y-3">
                  {selected.history.map((h) => (
                    <li key={h.id} className="text-sm border-l-2 border-white/10 pl-3">
                      <p className="text-white">{AUDIT_LABEL[h.action]?.(h.details) ?? h.action}</p>
                      {h.reason && <p className="text-gray-400">“{h.reason}”</p>}
                      <p className="text-xs text-gray-500">
                        {h.admin_name ?? "Unknown admin"} · {new Date(h.created_at).toLocaleString()}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </aside>
        </div>
      )}

      {pending && (() => {
        const d = describe(pending);
        return (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" className="bg-[#0b1426] border border-white/10 rounded-2xl max-w-md w-full p-6 space-y-4">
              <h3 id="confirm-title" className="text-lg font-bold">{d.title}</h3>
              <p className="text-sm text-gray-400">{d.effect}</p>
              <label htmlFor="action-reason" className="block text-xs text-gray-400">Reason (saved in the audit log)</label>
              <textarea
                id="action-reason"
                rows={3}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full bg-[#050b14] border border-white/10 rounded-xl p-3 text-sm focus:outline-none focus:border-blue-500"
              />
              <div className="flex justify-end gap-3">
                <button onClick={() => { setPending(null); setReason(""); }} className="px-4 py-2 text-sm text-gray-400 hover:text-white">
                  Cancel
                </button>
                <button
                  onClick={confirmAction}
                  disabled={saving || reason.trim().length < 3}
                  className={`px-4 py-2 text-sm font-semibold rounded-lg disabled:opacity-50 ${d.danger ? "bg-red-600 hover:bg-red-500" : "bg-emerald-600 hover:bg-emerald-500"}`}
                >
                  {saving ? "Saving…" : d.confirm}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </main>
  );
}
