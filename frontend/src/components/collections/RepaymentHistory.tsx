import Link from "next/link";

import { EmptyState } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { Collection } from "@/features/collections/types";
import { formatInr } from "@/lib/money";

export function RepaymentHistory({ rows }: { rows: Collection[] }) {
  if (rows.length === 0) return <EmptyState message="No repayments recorded yet." />;
  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-slate-50 text-slate-600">
          <tr><th scope="col" className="p-3">Receipt</th><th scope="col" className="p-3">Date</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3 text-right">Amount</th><th scope="col" className="p-3">Status</th><th scope="col" className="p-3"><span className="sr-only">Actions</span></th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className={`border-b last:border-0 ${r.status === "VOIDED" ? "text-slate-400 line-through" : ""}`}>
              <td className="p-3 font-mono text-xs">{r.receipt_number}</td>
              <td className="p-3">{new Date(r.collected_at).toLocaleString("en-IN")}</td>
              <td className="p-3">{r.agent.full_name || r.agent.username}</td>
              <td className="p-3 text-right">{formatInr(r.amount)}</td>
              <td className="p-3 no-underline"><StatusBadge status={r.status} /></td>
              <td className="p-3 no-underline"><Link className="text-xs underline" href={`/trace/collection/${r.id}`}>Trace</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
