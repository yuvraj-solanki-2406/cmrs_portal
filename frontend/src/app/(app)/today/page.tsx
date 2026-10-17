"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { collectionSummary } from "@/features/collections/api";
import { api, type Paginated } from "@/lib/apiClient";
import { formatInr } from "@/lib/money";
import type { Loan } from "@/features/lending/types";

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time

export default function TodayPage() {
  const due = useQuery({ queryKey: ["loans", { has_due: true }], queryFn: () => api<Paginated<Loan>>("/loans/", { query: { has_due: "true", page_size: 100 } }) });
  const summary = useQuery({ queryKey: ["collections", "summary", today()], queryFn: () => collectionSummary({ date_from: today(), date_to: today() }) });

  return (
    <section className="space-y-5">
      <h1 className="text-2xl font-semibold">Today</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="text-sm text-slate-500">Collected today</p>
          <p className="text-2xl font-semibold">{summary.data ? formatInr(summary.data.total_amount) : "—"}</p>
          <p className="text-xs text-slate-500">{summary.data?.count ?? 0} repayments · <Link className="underline" href="/collections">view all</Link></p>
        </div>
      </div>

      <h2 className="text-lg font-semibold">Customers with amounts due</h2>
      {due.isLoading && <Spinner />}
      {due.isError && <ErrorState error={due.error} onRetry={() => void due.refetch()} />}
      {due.data && due.data.results.length === 0 && <EmptyState message="Nothing is due right now." />}
      {due.data && due.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Customer</th><th scope="col" className="p-3">Loan</th><th scope="col" className="p-3 text-right">Due now</th><th scope="col" className="p-3 text-right">Outstanding</th><th scope="col" className="p-3"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {due.data.results.map((l) => (
                <tr key={l.id} className="border-b last:border-0">
                  <td className="p-3 font-medium"><Link className="underline" href={`/customers/${l.customer.id}`}>{l.customer.full_name}</Link></td>
                  <td className="p-3"><Link className="underline" href={`/loans/${l.id}`}>{l.loan_number}</Link></td>
                  <td className="p-3 text-right font-medium text-amber-700">{formatInr(l.due_now)}</td>
                  <td className="p-3 text-right">{formatInr(l.outstanding)}</td>
                  <td className="p-3 text-right"><Link href={`/collections/new?loan=${l.id}`} className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-1 text-xs text-white">Record</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
