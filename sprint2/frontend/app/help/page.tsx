"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { FAQS, searchFaqs } from "@/lib/faqs";
import { CATEGORY_LABELS, SupportCategory } from "@/lib/supportApi";
import { useAuth } from "@/contexts/AuthContext";

const FILTERS: (SupportCategory | "all")[] = ["all", "payment", "booking", "refund", "account"];

export default function HelpPage() {
  const { profile } = useAuth();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<SupportCategory | "all">("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const results = useMemo(() => {
    const base = query.trim() ? searchFaqs(query) : FAQS;
    return filter === "all" ? base : base.filter(f => f.category === filter);
  }, [query, filter]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Help Centre</h1>
      <p className="text-slate-400 mb-6">Find quick answers, or contact our support team.</p>

      <input
        type="search"
        className="input mb-4"
        placeholder="Search e.g. “refund”, “payment pending”, “ticket email”"
        value={query}
        onChange={e => setQuery(e.target.value)}
        aria-label="Search help articles"
      />

      <div className="flex flex-wrap gap-2 mb-6">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-sm px-3 py-1 rounded-full border transition-colors ${
              filter === f
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-slate-900 text-slate-300 border-slate-700 hover:border-blue-500"
            }`}
          >
            {f === "all" ? "All" : CATEGORY_LABELS[f]}
          </button>
        ))}
      </div>

      {results.length === 0 ? (
        <div className="card p-6 text-center text-slate-400">
          No answers match your search. Try other words, or contact us below.
        </div>
      ) : (
        <div className="space-y-3">
          {results.map(faq => {
            const isOpen = openId === faq.id;
            return (
              <div key={faq.id} className="rounded-2xl border border-slate-800 bg-slate-900">
                <button
                  onClick={() => setOpenId(isOpen ? null : faq.id)}
                  className="w-full flex justify-between items-center gap-4 text-left px-5 py-4 font-medium text-white"
                  aria-expanded={isOpen}
                >
                  <span>{faq.question}</span>
                  <span className="text-blue-400 text-xl leading-none">{isOpen ? "−" : "+"}</span>
                </button>
                {isOpen && (
                  <p className="px-5 pb-4 text-slate-300 text-sm leading-relaxed">{faq.answer}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="card p-6 mt-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-lg">Still need help?</h2>
          <p className="text-slate-400 text-sm">Raise a support request and our team will reply.</p>
        </div>
        <div className="flex gap-2">
          {profile && (
            <Link href="/support" className="btn-secondary text-sm">My Requests</Link>
          )}
          <Link href={profile ? "/support/new" : "/auth/login"} className="btn-primary text-sm">
            {profile ? "Contact Support" : "Login to Contact Us"}
          </Link>
        </div>
      </div>
    </div>
  );
}
