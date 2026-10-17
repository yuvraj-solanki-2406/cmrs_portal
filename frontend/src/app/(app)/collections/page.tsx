"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { inputClass } from "@/components/ui/form";
import { ReasonDialog } from "@/components/ui/ReasonDialog";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { CsvButton } from "@/components/reporting/CsvButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { collectionSummary, listCollections, voidCollection } from "@/features/collections/api";
import type { Collection } from "@/features/collections/types";
import { listAgents } from "@/features/lending/api";
import { ApiError } from "@/lib/apiClient";
import { formatInr } from "@/lib/money";

const today = () => new Date().toLocaleDateString("en-CA");

export default function CollectionsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState(today());
  const [dateTo, setDateTo] = useState(today());
  const [agent, setAgent] = useState("");
  const [status, setStatus] = useState("");
  const [voiding, setVoiding] = useState<Collection | null>(null);
  const [voidError, setVoidError] = useState<string | null>(null);

  const isManager = user?.role === "BRANCH_MANAGER";
  const filters = { page, agent, status, date_from: dateFrom, date_to: dateTo };
  const list = useQuery({ queryKey: ["collections", filters], queryFn: () => listCollections(filters), placeholderData: keepPreviousData });
  const summary = useQuery({ queryKey: ["collections", "summary", filters], queryFn: () => collectionSummary(filters) });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => listAgents(), enabled: user?.role === "BRANCH_MANAGER" || user?.role === "ADMIN" });

  const voidMutation = useMutation({
    mutationFn: (reason: string) => voidCollection(voiding!.id, reason),
    onSuccess: () => { setVoiding(null); setVoidError(null); void qc.invalidateQueries({ queryKey: ["collections"] }); void qc.invalidateQueries({ queryKey: ["loan"] }); void qc.invalidateQueries({ queryKey: ["loans"] }); },
    onError: (err) => setVoidError(err instanceof ApiError ? err.userMessage : "Could not void."),
  });

  if (!user) return null;
  const reset = () => setPage(1);

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">{user.role === "AGENT" ? "My Collections" : "Collections"}</h1>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">From<input type="date" className={`${inputClass} mt-1`} value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); reset(); }} /></label>
        <label className="text-sm">To<input type="date" className={`${inputClass} mt-1`} value={dateTo} onChange={(e) => { setDateTo(e.target.value); reset(); }} /></label>
        {agents.data && (
          <label className="text-sm">Agent
            <select className={`${inputClass} mt-1`} value={agent} onChange={(e) => { setAgent(e.target.value); reset(); }}>
              <option value="">All</option>{agents.data.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
            </select>
          </label>
        )}
        <label className="text-sm">Status
          <select className={`${inputClass} mt-1`} value={status} onChange={(e) => { setStatus(e.target.value); reset(); }}>
            <option value="">All</option><option value="VALID">Valid</option><option value="VOIDED">Voided</option>
          </select>
        </label>
        <span className="ml-auto flex items-center gap-2">
          <CsvButton path="/export/collections.csv" query={{ agent: agent || undefined, status: status || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }} filename="collections.csv" />
          {user.role === "AGENT" && <Link href="/today" className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-2 text-sm text-white">Record repayment</Link>}
        </span>
      </div>

      <div className="rounded-lg bg-white p-4 shadow-sm">
        <p className="text-sm text-slate-500">Total (valid) for selected filters</p>
        <p className="text-2xl font-semibold">{summary.data ? formatInr(summary.data.total_amount) : "—"} <span className="text-sm font-normal text-slate-500">{summary.data?.count ?? 0} repayments</span></p>
      </div>

      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState message="No collections for these filters." />}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Receipt</th><th scope="col" className="p-3">Customer</th><th scope="col" className="p-3">Loan</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3 text-right">Amount</th><th scope="col" className="p-3">Status</th><th scope="col" className="p-3"><span className="sr-only">Actions</span></th>{isManager && <th scope="col" className="p-3"><span className="sr-only">Actions</span></th>}</tr>
            </thead>
            <tbody>
              {list.data.results.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="p-3 font-mono text-xs">{c.receipt_number}</td>
                  <td className="p-3">{c.customer.full_name}</td>
                  <td className="p-3"><Link className="underline" href={`/loans/${c.loan.id}`}>{c.loan.loan_number}</Link></td>
                  <td className="p-3">{c.agent.full_name || c.agent.username}</td>
                  <td className="p-3 text-right">{formatInr(c.amount)}</td>
                  <td className="p-3"><StatusBadge status={c.status} /></td>
                  <td className="p-3"><Link className="text-xs underline" href={`/trace/collection/${c.id}`}>Trace</Link></td>
                  {isManager && <td className="p-3 text-right">{c.status === "VALID" && <button className="text-xs underline" onClick={() => { setVoiding(c); setVoidError(null); }}>Void</button>}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600">
            <span>{list.data.count} records</span>
            <div className="space-x-2">
              <button disabled={!list.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button>
              <button disabled={!list.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>
      )}

      <ReasonDialog open={voiding !== null} title={`Void ${voiding?.receipt_number ?? ""}?`}
        description={voiding ? `${formatInr(voiding.amount)} from ${voiding.customer.full_name} will be removed from the loan balance. This cannot be undone.` : ""}
        actionLabel="Void collection" error={voidError} busy={voidMutation.isPending}
        onCancel={() => { setVoiding(null); setVoidError(null); }} onSubmit={(r) => voidMutation.mutate(r)} />
    </section>
  );
}
