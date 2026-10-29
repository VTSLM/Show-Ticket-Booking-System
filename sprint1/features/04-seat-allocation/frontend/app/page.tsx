import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 p-8 md:p-16">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-bold text-slate-900">Seat Allocation</h1>
        <p className="mt-3 text-slate-600">
          Choose a workflow to continue.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <Link href="/shows/11111111-1111-1111-1111-111111111111/seats"
            className="rounded-xl border bg-white p-6 shadow-sm hover:border-slate-400">
            <h2 className="text-xl font-semibold">Customer Seat Selection</h2>
            <p className="mt-2 text-sm text-slate-600">View a show’s seat map and select seats.</p>
          </Link>
          <Link href="/manager/layouts"
            className="rounded-xl border bg-white p-6 shadow-sm hover:border-slate-400">
            <h2 className="text-xl font-semibold">Manager Layout & Pricing</h2>
            <p className="mt-2 text-sm text-slate-600">Create layouts, set prices, and block seats.</p>
          </Link>
        </div>
      </div>
    </main>
  );
}
