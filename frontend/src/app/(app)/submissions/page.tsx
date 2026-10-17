"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { CsvButton } from "@/components/reporting/CsvButton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { listSubmissions } from "@/features/cash/api";
import { listAgents } from "@/features/lending/api";
import { formatInr } from "@/lib/money";

export default function SubmissionsPage() {
  const { user } = useAuth();
  const isManager = user?.role === "BRANCH_MANAGER";
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState(isManager ? "SUBMITTED" : "");
  const [agent, setAgent] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const filters = { page, status, agent, date_from: dateFrom, date_to: dateTo };
  const list = useQuery({ queryKey: ["submissions", filters], queryFn: () => listSubmissions(filters), placeholderData: keepPreviousData });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => listAgents(), enabled: user?.role === "BRANCH_MANAGER" || user?.role === "ADMIN" });
  if (!user) return null;
  const reset = () => setPage(1);
  const title = user.role === "AGENT" ? "My Submissions" : isManager ? "Reconciliation" : "Cash Submissions";

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">Status
          <select className={`${inputClass} mt-1`} value={status} onChange={(e) => { setStatus(e.target.value); reset(); }}>
            <option value="">All</option><option value="SUBMITTED">Submitted (pending)</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option>
          </select>
        </label>
        {agents.data && (
          <label className="text-sm">Agent
            <select className={`${inputClass} mt-1`} value={agent} onChange={(e) => { setAgent(e.target.value); reset(); }}>
              <option value="">All</option>{agents.data.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
            </select>
          </label>
        )}
        <label className="text-sm">From<input type="date" className={`${inputClass} mt-1`} value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); reset(); }} /></label>
        <label className="text-sm">To<input type="date" className={`${inputClass} mt-1`} value={dateTo} onChange={(e) => { setDateTo(e.target.value); reset(); }} /></label>
        <span className="ml-auto flex items-center gap-2">
          <CsvButton path="/export/submissions.csv" query={{ status: status || undefined, agent: agent || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }} filename="submissions.csv" />
          {user.role === "AGENT" && <Link href="/cash" className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-2 text-sm text-white">Submit cash</Link>}
        </span>
      </div>

      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState message={isManager && status === "SUBMITTED" ? "No submissions are waiting for reconciliation." : "No submissions found."} />}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Reference</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3">Submitted</th><th scope="col" className="p-3 text-right">Expected</th><th scope="col" className="p-3 text-right">Received</th><th scope="col" className="p-3 text-right">Difference</th><th scope="col" className="p-3">Status</th></tr>
            </thead>
            <tbody>
              {list.data.results.map((s) => (
                <tr key={s.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="p-3 font-mono text-xs"><Link className="underline" href={`/submissions/${s.id}`}>{s.reference_no}</Link></td>
                  <td className="p-3">{s.agent.full_name || s.agent.username}</td>
                  <td className="p-3">{new Date(s.submitted_at).toLocaleString("en-IN")}</td>
                  <td className="p-3 text-right">{formatInr(s.expected_amount)}</td>
                  <td className="p-3 text-right">{formatInr(s.received_amount)}</td>
                  <td className={`p-3 text-right font-medium ${s.discrepancy_amount && s.discrepancy_amount !== "0.00" ? "text-red-700" : ""}`}>{formatInr(s.discrepancy_amount)}</td>
                  <td className="p-3"><StatusBadge status={s.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600">
            <span>{list.data.count} submissions</span>
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
