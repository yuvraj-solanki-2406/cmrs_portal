"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { SettlementBadges, VarianceChip } from "@/components/ui/DepositBadges";
import { CsvButton } from "@/components/reporting/CsvButton";
import { inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { listDeposits } from "@/features/treasury/api";
import { formatInr } from "@/lib/money";

const TABS = [
  { key: "all", label: "All", query: {} },
  { key: "pending", label: "Pending", query: { status: "PENDING" } },
  { key: "delayed", label: "Delayed", query: { delayed: "true" } },
  { key: "failed", label: "Failed", query: { status: "FAILED" } },
  { key: "settled", label: "Settled", query: { status: "SETTLED" } },
];

export default function DepositsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState(user?.role === "FINANCE" ? "pending" : "all");
  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const filters = { page, date_from: dateFrom, date_to: dateTo, ...TABS.find((t) => t.key === tab)!.query };
  const list = useQuery({ queryKey: ["deposits", filters], queryFn: () => listDeposits(filters), placeholderData: keepPreviousData });
  if (!user) return null;
  const isFinance = user.role === "FINANCE";

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{isFinance ? "Settlements" : "Bank Deposits"}</h1>
        {user.role === "BRANCH_MANAGER" && <Link href="/deposits/new" className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-2 text-sm text-white">New deposit</Link>}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex rounded border border-slate-300 bg-white text-sm">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => { setTab(t.key); setPage(1); }}
              className={`px-3 py-2 ${tab === t.key ? "bg-ink text-white" : "text-slate-700 hover:bg-slate-100"}`}>{t.label}</button>
          ))}
        </div>
        <label className="text-sm">From<input type="date" className={`${inputClass} mt-1`} value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} /></label>
        <label className="text-sm">To<input type="date" className={`${inputClass} mt-1`} value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} /></label>
        <span className="ml-auto"><CsvButton path="/export/deposits.csv" query={{ status: (filters as { status?: string }).status, delayed: (filters as { delayed?: string }).delayed, date_from: dateFrom || undefined, date_to: dateTo || undefined }} filename="deposits.csv" /></span>
      </div>

      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState message="No deposits match this view." />}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Deposit</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Bank / reference</th><th scope="col" className="p-3">Date</th><th scope="col" className="p-3 text-right">Reconciled</th><th scope="col" className="p-3 text-right">Deposited</th><th scope="col" className="p-3 text-right">Settled</th><th scope="col" className="p-3">Gap</th><th scope="col" className="p-3">Status</th></tr>
            </thead>
            <tbody>
              {list.data.results.map((d) => (
                <tr key={d.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="p-3 font-mono text-xs"><Link className="underline" href={`/deposits/${d.id}`}>{d.deposit_no}</Link></td>
                  <td className="p-3">{d.branch}</td>
                  <td className="p-3">{d.bank_name} · <span className="font-mono text-xs">{d.reference_number}</span></td>
                  <td className="p-3">{d.deposit_date}</td>
                  <td className="p-3 text-right">{formatInr(d.reconciled_amount)}</td>
                  <td className="p-3 text-right">{formatInr(d.amount)}</td>
                  <td className="p-3 text-right">{formatInr(d.settlement.settled_amount)}</td>
                  <td className="p-3"><VarianceChip amount={d.gap_amount ?? (d.variance_amount !== "0.00" ? d.variance_amount : null)} /></td>
                  <td className="p-3"><SettlementBadges deposit={d} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600">
            <span>{list.data.count} deposits</span>
            <div className="space-x-2">
              <button disabled={!list.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button>
              <button disabled={!list.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
