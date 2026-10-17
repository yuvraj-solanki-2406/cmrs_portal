"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense } from "react";

import { CsvButton } from "@/components/reporting/CsvButton";
import { FilterBar, toQuery, type FilterValues } from "@/components/reporting/FilterBar";
import { useUrlFilters } from "@/components/reporting/useUrlFilters";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getMismatches } from "@/features/reporting/api";
import { formatInr } from "@/lib/money";

const LABELS: Record<string, string> = {
  DEPOSIT_VS_RECONCILED: "Deposit ≠ reconciled cash", SETTLED_VS_DEPOSITED: "Bank credit ≠ deposit",
  SETTLEMENT_FAILED: "Settlement failed", SETTLEMENT_DELAYED: "Settlement delayed",
};

function Report() {
  const [values, setValues] = useUrlFilters<FilterValues>({ date_from: "", date_to: "", branch: "", agent: "", stage: "" });
  const query = toQuery(values);
  const list = useQuery({ queryKey: ["report", "mismatches", query], queryFn: () => getMismatches(query) });
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-2xl font-semibold">Deposit &amp; settlement mismatches</h1>
        <CsvButton path="/reports/mismatches.csv" query={{ ...query, stage: undefined }} filename="mismatches.csv" /></div>
      <p className="text-sm text-slate-600">Where branch-reconciled cash, bank deposits and bank-settled amounts disagree, plus failed and delayed settlements.</p>
      <FilterBar values={values} onChange={setValues} />
      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.rows.length === 0 && <EmptyState message="No mismatches. Everything reconciles." />}
      {list.data && list.data.rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Type</th><th scope="col" className="p-3">Deposit</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Date</th><th scope="col" className="p-3 text-right">Expected</th><th scope="col" className="p-3 text-right">Actual</th><th scope="col" className="p-3 text-right">Difference</th><th scope="col" className="p-3">Reason</th><th scope="col" className="p-3">Settlement</th></tr></thead>
            <tbody>
              {list.data.rows.map((r, i) => (
                <tr key={`${r.deposit_id}-${r.type}-${i}`} className="border-b last:border-0">
                  <td className="p-3">{LABELS[r.type]}</td>
                  <td className="p-3 font-mono text-xs"><Link className="underline" href={`/deposits/${r.deposit_id}`}>{r.deposit_no}</Link></td>
                  <td className="p-3">{r.branch}</td><td className="p-3">{r.date}</td>
                  <td className="p-3 text-right">{formatInr(r.expected)}</td><td className="p-3 text-right">{formatInr(r.actual)}</td>
                  <td className="p-3 text-right font-medium text-red-700">{r.difference ? formatInr(r.difference) : "—"}</td>
                  <td className="p-3">{r.reason}</td><td className="p-3"><StatusBadge status={r.settlement_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function MismatchesPage() { return <Suspense fallback={<Spinner />}><Report /></Suspense>; }
