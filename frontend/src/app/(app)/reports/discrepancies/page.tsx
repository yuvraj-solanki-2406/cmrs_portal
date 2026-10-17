"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense, useState } from "react";

import { CsvButton } from "@/components/reporting/CsvButton";
import { FilterBar, toQuery, type FilterValues } from "@/components/reporting/FilterBar";
import { useUrlFilters } from "@/components/reporting/useUrlFilters";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { getDiscrepancies } from "@/features/reporting/api";
import { formatInr } from "@/lib/money";

function Report() {
  const [values, setValues] = useUrlFilters<FilterValues>({ date_from: "", date_to: "", branch: "", agent: "", stage: "" });
  const [page, setPage] = useState(1);
  const query = toQuery(values);
  const list = useQuery({ queryKey: ["report", "discrepancies", query, page], queryFn: () => getDiscrepancies({ ...query, page }), placeholderData: keepPreviousData });
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-2xl font-semibold">Discrepancy report</h1>
        <CsvButton path="/reports/discrepancies.csv" query={{ ...query, stage: undefined }} filename="discrepancies.csv" /></div>
      <p className="text-sm text-slate-600">Branch counts that differed from what the agent submitted. Positive = shortfall, negative = surplus.</p>
      <FilterBar values={values} onChange={(p) => { setValues(p); setPage(1); }} />
      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState message="No discrepancies for these filters." />}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Submission</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3">Reviewed</th><th scope="col" className="p-3 text-right">Expected</th><th scope="col" className="p-3 text-right">Received</th><th scope="col" className="p-3 text-right">Difference</th><th scope="col" className="p-3">Reason</th></tr></thead>
            <tbody>
              {list.data.results.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="p-3 font-mono text-xs"><Link className="underline" href={`/submissions/${r.id}`}>{r.reference_no}</Link></td>
                  <td className="p-3">{r.branch}</td><td className="p-3">{r.agent}</td><td className="p-3">{new Date(r.reviewed_at).toLocaleDateString("en-IN")} by {r.reviewed_by}</td>
                  <td className="p-3 text-right">{formatInr(r.expected_amount)}</td><td className="p-3 text-right">{formatInr(r.received_amount)}</td>
                  <td className="p-3 text-right font-medium text-red-700">{formatInr(r.discrepancy_amount)}</td><td className="p-3">{r.discrepancy_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600"><span>{list.data.count} cases</span>
            <div className="space-x-2"><button disabled={!list.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button><button disabled={!list.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button></div></div>
        </div>
      )}
    </section>
  );
}

export default function DiscrepanciesPage() { return <Suspense fallback={<Spinner />}><Report /></Suspense>; }
