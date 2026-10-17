import { StatusBadge } from "@/components/ui/StatusBadge";
import type { Installment } from "@/features/lending/types";
import { formatInr } from "@/lib/money";

export function InstallmentTable({ rows }: { rows: Installment[] }) {
  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-slate-50 text-slate-600">
          <tr><th scope="col" className="p-3">#</th><th scope="col" className="p-3">Due date</th><th scope="col" className="p-3 text-right">Amount due</th>
            <th scope="col" className="p-3 text-right">Paid</th><th scope="col" className="p-3 text-right">Remaining</th><th scope="col" className="p-3">Status</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b last:border-0">
              <td className="p-3">{r.installment_no}</td>
              <td className="p-3">{r.due_date}</td>
              <td className="p-3 text-right">{formatInr(r.amount_due)}</td>
              <td className="p-3 text-right">{formatInr(r.amount_paid)}</td>
              <td className="p-3 text-right">{formatInr(r.amount_remaining)}</td>
              <td className="p-3"><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
