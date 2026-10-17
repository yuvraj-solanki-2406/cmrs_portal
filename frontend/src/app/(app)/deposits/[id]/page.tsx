"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { SettlementBadges } from "@/components/ui/DepositBadges";
import { Field, Input, MoneyInput, PrimaryButton } from "@/components/ui/form";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ReasonDialog } from "@/components/ui/ReasonDialog";
import { ErrorState, Spinner } from "@/components/ui/states";
import { useAuth } from "@/features/auth/AuthProvider";
import { confirmSettlement, failSettlement, getDeposit } from "@/features/treasury/api";
import { ApiError } from "@/lib/apiClient";
import { MONEY_PATTERN, formatInr, subtractMoney } from "@/lib/money";

export default function DepositDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();
  const dep = useQuery({ queryKey: ["deposit", id], queryFn: () => getDeposit(id) });
  const today = new Date().toLocaleDateString("en-CA");
  const [settled, setSettled] = useState<string | null>(null);
  const [settledOn, setSettledOn] = useState(today);
  const [creditRef, setCreditRef] = useState("");
  const [note, setNote] = useState("");
  const [dialog, setDialog] = useState<"confirm" | "fail" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const done = () => { setDialog(null); setError(null); void qc.invalidateQueries({ queryKey: ["deposit", id] }); void qc.invalidateQueries({ queryKey: ["deposits"] }); };
  const onError = (err: unknown) => { setDialog(null); setError(err instanceof ApiError ? err.userMessage : "Something went wrong."); };

  if (dep.isLoading) return <Spinner />;
  if (dep.isError) return <ErrorState error={dep.error} onRetry={() => void dep.refetch()} />;
  const d = dep.data!;
  const s = d.settlement;
  const settledAmount = settled ?? d.amount; // defaults to what was deposited
  const validSettled = MONEY_PATTERN.test(settledAmount) && settledAmount !== "0.00" && settledAmount !== "0";
  const variance = validSettled ? subtractMoney(d.amount, settledAmount) : null; // deposited − credited
  const hasVariance = variance !== null && variance !== "0.00";
  const canAct = user?.role === "FINANCE" && s.status !== "SETTLED";

  const confirm = () => confirmSettlement(Number(id), { settled_amount: settledAmount, settled_on: settledOn, variance_note: note, bank_credit_reference: creditRef })
    .then(done).catch(onError);
  const fail = (reason: string) => failSettlement(Number(id), reason).then(done).catch(onError);

  return (
    <section className="space-y-6">
      <div>
        <Link href="/deposits" className="text-sm text-slate-500 underline">← Deposits</Link>
        <h1 className="mt-1 text-2xl font-semibold"><span className="font-mono text-xl">{d.deposit_no}</span> <SettlementBadges deposit={d} /> <Link href={`/trace/deposit/${d.id}`} className="ml-2 text-sm font-normal underline">Lifecycle trace</Link></h1>
      </div>

      <div className="grid gap-4 rounded-lg bg-white p-4 text-sm shadow-sm md:grid-cols-4">
        <div><p className="text-slate-500">Bank / reference</p><p>{d.bank_name} · <span className="font-mono text-xs">{d.reference_number}</span></p></div>
        <div><p className="text-slate-500">Deposit date</p><p>{d.deposit_date}</p></div>
        <div><p className="text-slate-500">Reconciled cash</p><p className="text-lg font-semibold">{formatInr(d.reconciled_amount)}</p></div>
        <div><p className="text-slate-500">Deposited</p><p className="text-lg font-semibold">{formatInr(d.amount)}</p></div>
        {d.variance_amount !== "0.00" && <div className="rounded bg-red-50 p-3 md:col-span-4"><p className="font-medium text-red-800">Deposit variance {formatInr(d.variance_amount)}</p><p className="text-red-700">{d.variance_note}</p></div>}
        {s.status === "SETTLED" && (
          <div className={`rounded p-3 md:col-span-4 ${s.variance_amount !== "0.00" ? "bg-red-50" : "bg-green-50"}`}>
            <p className="font-medium">Settled {formatInr(s.settled_amount)} on {s.settled_on} (confirmed by {s.confirmed_by}){s.bank_credit_reference && ` · credit ref ${s.bank_credit_reference}`}</p>
            {s.variance_amount !== "0.00" && <p className="text-red-800">Bank credit differs from the deposit by {formatInr(s.variance_amount)}: {s.variance_note}</p>}
            {d.gap_amount && d.gap_amount !== "0.00" && <p className="text-red-800">Reconciled minus bank-settled: {formatInr(d.gap_amount)}</p>}
            {s.failure_reason && <p className="text-xs text-slate-600">Earlier failure: {s.failure_reason}</p>}
          </div>
        )}
        {s.status === "FAILED" && <div className="rounded bg-red-50 p-3 md:col-span-4"><p className="font-medium text-red-800">Settlement failed</p><p className="text-red-700">{s.failure_reason}</p></div>}
        {d.is_delayed && <div className="rounded bg-orange-50 p-3 text-orange-800 md:col-span-4">Settlement is still pending past the allowed window.</div>}
      </div>

      {canAct && (
        <div className="max-w-xl space-y-3 rounded-lg border border-tertiary bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold">{s.status === "FAILED" ? "Retry settlement" : "Settlement"}</h2>
          <p className="text-sm text-slate-600">Enter what the bank actually credited to the company account.</p>
          <Field label="Amount credited (₹)" error={settled !== null && !validSettled ? "Enter an amount like 48500 or 48500.50" : undefined}><MoneyInput value={settledAmount} onChange={setSettled} /></Field>
          <Field label="Credited on"><Input type="date" min={d.deposit_date} max={today} value={settledOn} onChange={(e) => setSettledOn(e.target.value)} /></Field>
          <Field label="Bank credit reference (optional)"><Input value={creditRef} maxLength={60} onChange={(e) => setCreditRef(e.target.value)} /></Field>
          {validSettled && <p className={`rounded p-2 text-sm font-medium ${hasVariance ? "bg-red-50 text-red-800" : "bg-green-50 text-green-800"}`}>Deposited {formatInr(d.amount)} · Credited {formatInr(settledAmount)} · {hasVariance ? `Variance ${formatInr(variance!)}` : "Matches exactly"}</p>}
          {hasVariance && <Field label="Reason for the difference (required)"><Input value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} /></Field>}
          {error && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <PrimaryButton disabled={!validSettled || (hasVariance && !note.trim())} onClick={() => setDialog("confirm")}>Confirm settlement</PrimaryButton>
            {s.status === "PENDING" && <button className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50" onClick={() => setDialog("fail")}>Mark failed…</button>}
          </div>
        </div>
      )}
      {!canAct && error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div>
        <h2 className="mb-2 text-lg font-semibold">Covered submissions ({d.submissions?.length ?? 0})</h2>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Submission</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3 text-right">Received</th><th scope="col" className="p-3 text-right">Discrepancy</th></tr></thead>
            <tbody>
              {d.submissions?.map((x) => (
                <tr key={x.id} className="border-b last:border-0">
                  <td className="p-3 font-mono text-xs"><Link className="underline" href={`/submissions/${x.id}`}>{x.reference_no}</Link></td>
                  <td className="p-3">{x.agent}</td><td className="p-3 text-right">{formatInr(x.received_amount)}</td>
                  <td className={`p-3 text-right ${x.discrepancy_amount !== "0.00" ? "font-medium text-red-700" : ""}`}>{formatInr(x.discrepancy_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog open={dialog === "confirm"} title="Confirm settlement"
        message={`Mark ${d.deposit_no} as settled with ${formatInr(settledAmount)} credited${hasVariance ? ` (variance ${formatInr(variance!)})` : ""}? Settled records are final.`}
        confirmLabel="Confirm" onCancel={() => setDialog(null)} onConfirm={() => void confirm()} />
      <ReasonDialog open={dialog === "fail"} title="Mark settlement failed"
        description="You can still confirm it later if the bank credit appears."
        actionLabel="Mark failed" onCancel={() => setDialog(null)} onSubmit={(r) => void fail(r)} />
    </section>
  );
}
