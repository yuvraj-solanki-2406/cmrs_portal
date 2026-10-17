"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { getLifecycle } from "@/features/reporting/api";
import { formatInr } from "@/lib/money";

const when = (v: string | null) => (v ? new Date(v).toLocaleString("en-IN") : "—");

function Step({ title, tone = "bg-tertiary", children }: { title: string; tone?: string; children: React.ReactNode }) {
  return (
    <div className="relative border-l-2 border-tertiary pb-6 pl-6">
      <span className={`absolute -left-[9px] top-1 h-4 w-4 rounded-full ${tone}`} />
      <h2 className="mb-2 text-lg font-semibold">{title}</h2>
      {children}
    </div>
  );
}

export default function TracePage() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const trace = useQuery({ queryKey: ["trace", type, id], queryFn: () => getLifecycle(type, id) });
  if (trace.isLoading) return <Spinner />;
  if (trace.isError) return <ErrorState error={trace.error} onRetry={() => void trace.refetch()} />;
  const t = trace.data!;
  const limited = t.deposits.some((d) => d.amount === undefined);

  return (
    <section className="space-y-4">
      <div><h1 className="text-2xl font-semibold">Lifecycle trace</h1><p className="text-sm text-slate-600">From the customer&apos;s repayment to the bank settlement, with who did what and when. Traced from a {t.root.type} (#{t.root.id}).</p></div>

      <Step title={`1. Customer repayment${t.collections.length > 1 ? "s" : ""} (${t.collections.length})`}>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm"><table className="w-full text-left text-sm">
          <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Receipt</th><th scope="col" className="p-3">Customer</th><th scope="col" className="p-3">Loan</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3">Recorded</th><th scope="col" className="p-3 text-right">Amount</th><th scope="col" className="p-3">Status</th></tr></thead>
          <tbody>{t.collections.map((c) => (
            <tr key={c.id} className="border-b last:border-0"><td className="p-3 font-mono text-xs">{c.receipt_number}</td><td className="p-3">{c.customer}</td><td className="p-3">{c.loan_number}</td><td className="p-3">{c.agent}</td><td className="p-3">{when(c.collected_at)}</td><td className="p-3 text-right">{formatInr(c.amount)}</td><td className="p-3"><StatusBadge status={c.status} />{c.void_reason && <span className="ml-1 text-xs text-slate-500">{c.void_reason}</span>}</td></tr>))}</tbody>
        </table></div>
        <p className="mt-1 text-xs text-slate-500">Recording a repayment credits the customer&apos;s loan. It does not mean the cash has reached the branch.</p>
      </Step>

      <Step title={`2. Cash submission & branch reconciliation (${t.submissions.length})`} tone={t.submissions.length ? "bg-tertiary" : "bg-slate-300"}>
        {t.submissions.length === 0 ? <p className="text-sm text-slate-600">Not submitted to the branch yet: the agent is still holding this cash.</p> : (
          <div className="space-y-2">{t.submissions.map((s) => (
            <div key={s.id} className="rounded-lg bg-white p-3 text-sm shadow-sm">
              <p className="flex flex-wrap items-center gap-2"><Link className="font-mono text-xs underline" href={`/submissions/${s.id}`}>{s.reference_no}</Link><StatusBadge status={s.status} /> by {s.agent} · {when(s.submitted_at)}</p>
              <p>Expected {formatInr(s.expected_amount)} · Counted {formatInr(s.received_amount)}{s.discrepancy_amount && s.discrepancy_amount !== "0.00" && <span className="ml-1 font-medium text-red-700">· difference {formatInr(s.discrepancy_amount)} ({s.discrepancy_reason})</span>}</p>
              {s.reviewed_by && <p className="text-slate-600">Reviewed by {s.reviewed_by} · {when(s.reviewed_at)}{s.rejection_reason && ` · rejected: ${s.rejection_reason}`}</p>}
            </div>))}</div>)}
      </Step>

      <Step title="3. Bank deposit & settlement" tone={t.deposits.length ? "bg-tertiary" : "bg-slate-300"}>
        {t.deposits.length === 0 ? <p className="text-sm text-slate-600">Not deposited at the bank yet.</p> : t.deposits.map((d) => (
          <div key={d.id} className="rounded-lg bg-white p-3 text-sm shadow-sm">
            <p className="flex flex-wrap items-center gap-2">{limited ? <span className="font-mono text-xs">{d.deposit_no}</span> : <Link className="font-mono text-xs underline" href={`/deposits/${d.id}`}>{d.deposit_no}</Link>}<StatusBadge status={d.settlement_status} />{d.is_delayed && <StatusBadge status="DELAYED" />} {d.bank_name} · deposited {d.deposit_date}</p>
            {!limited && <p>Reconciled {formatInr(d.reconciled_amount)} · Deposited {formatInr(d.amount)} · ref {d.reference_number}{d.variance_amount && d.variance_amount !== "0.00" && <span className="ml-1 font-medium text-red-700">· variance {formatInr(d.variance_amount)} ({d.variance_note})</span>}</p>}
            {d.settlement_status === "SETTLED" && <p>{!limited && <>Bank credited {formatInr(d.settled_amount)} · </>}settled on {d.settled_on}{!limited && d.settlement_variance && d.settlement_variance !== "0.00" && <span className="ml-1 font-medium text-red-700">· variance {formatInr(d.settlement_variance)} ({d.settlement_variance_note})</span>}</p>}
            {d.settlement_status === "FAILED" && <p className="text-red-700">Failed: {d.failure_reason}</p>}
          </div>))}
        {limited && t.deposits.length > 0 && <p className="mt-1 text-xs text-slate-500">Amounts are hidden because a deposit can include cash from several agents.</p>}
      </Step>

      <Step title="Audit trail">
        {t.timeline.length === 0 ? <p className="text-sm text-slate-600">No events.</p> : (
          <ol className="space-y-1 text-sm">{t.timeline.map((e, i) => (
            <li key={i} className="rounded bg-white p-2 shadow-sm"><span className="text-xs text-slate-500">{when(e.at)}</span> · <b>{e.action.replaceAll("_", " ")}</b> · {e.actor ?? "system"} <span className="text-xs text-slate-500">({e.actor_role})</span>{e.reason && <span className="text-slate-600"> — {e.reason}</span>}</li>))}</ol>)}
      </Step>
    </section>
  );
}
