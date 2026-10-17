"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ReasonDialog } from "@/components/ui/ReasonDialog";
import { Field, Input, MoneyInput, PrimaryButton } from "@/components/ui/form";
import { ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { approveSubmission, getSubmission, rejectSubmission } from "@/features/cash/api";
import { ApiError } from "@/lib/apiClient";
import { MONEY_PATTERN, formatInr, subtractMoney } from "@/lib/money";

export default function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();
  const sub = useQuery({ queryKey: ["submission", id], queryFn: () => getSubmission(id) });
  const [received, setReceived] = useState("");
  const [reason, setReason] = useState("");
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => { void qc.invalidateQueries({ queryKey: ["submission", id] }); void qc.invalidateQueries({ queryKey: ["submissions"] }); };
  const onError = (err: unknown) => { setDialog(null); setError(err instanceof ApiError ? err.userMessage : "Something went wrong."); };
  const approve = useMutation({ mutationFn: () => approveSubmission(Number(id), received, reason), onSuccess: () => { setDialog(null); setError(null); refresh(); }, onError });
  const reject = useMutation({ mutationFn: (reason: string) => rejectSubmission(Number(id), reason), onSuccess: () => { setDialog(null); setError(null); refresh(); }, onError });

  if (sub.isLoading) return <Spinner />;
  if (sub.isError) return <ErrorState error={sub.error} onRetry={() => void sub.refetch()} />;
  const s = sub.data!;
  const canReview = user?.role === "BRANCH_MANAGER" && s.status === "SUBMITTED";
  const validReceived = MONEY_PATTERN.test(received);
  const diff = validReceived ? subtractMoney(s.expected_amount, received) : null; // + shortfall, - surplus
  const hasDiff = diff !== null && diff !== "0.00";
  const reasonMissing = hasDiff && !reason.trim();

  return (
    <section className="space-y-6">
      <div>
        <Link href="/submissions" className="text-sm text-slate-500 underline">← Submissions</Link>
        <h1 className="mt-1 text-2xl font-semibold"><span className="font-mono text-xl">{s.reference_no}</span> <StatusBadge status={s.status} /> <Link href={`/trace/submission/${s.id}`} className="ml-2 text-sm font-normal underline">Lifecycle trace</Link></h1>
      </div>

      <div className="grid gap-4 rounded-lg bg-white p-4 text-sm shadow-sm md:grid-cols-4">
        <div><p className="text-slate-500">Agent</p><p>{s.agent.full_name || s.agent.username}</p></div>
        <div><p className="text-slate-500">Submitted</p><p>{new Date(s.submitted_at).toLocaleString("en-IN")}</p></div>
        <div><p className="text-slate-500">Expected</p><p className="text-lg font-semibold">{formatInr(s.expected_amount)}</p></div>
        <div><p className="text-slate-500">Received (counted)</p><p className="text-lg font-semibold">{formatInr(s.received_amount)}</p></div>
        {s.discrepancy_amount && s.discrepancy_amount !== "0.00" && (
          <div className="rounded bg-red-50 p-3 md:col-span-4">
            <p className="font-medium text-red-800">{Number(s.discrepancy_amount) > 0 ? "Shortfall" : "Surplus"} of {formatInr(s.discrepancy_amount.replace("-", ""))}</p>
            <p className="text-red-700">{s.discrepancy_reason}</p>
          </div>
        )}
        {s.status === "REJECTED" && <div className="rounded bg-red-50 p-3 md:col-span-4"><p className="font-medium text-red-800">Rejected by {s.reviewed_by}</p><p className="text-red-700">{s.rejection_reason}</p><p className="text-xs text-red-700">The collections are back in your Cash Holding and can be submitted again.</p></div>}
        {s.status === "APPROVED" && <div className="md:col-span-4 text-slate-600">Approved by {s.reviewed_by} on {s.reviewed_at && new Date(s.reviewed_at).toLocaleString("en-IN")}. This record is final and cannot be changed.</div>}
        {s.note && <div className="md:col-span-4"><p className="text-slate-500">Agent note</p><p>{s.note}</p></div>}
      </div>

      {canReview && (
        <div className="max-w-xl space-y-3 rounded-lg border border-tertiary bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold">Reconcile</h2>
          <p className="text-sm text-slate-600">Count the cash handed over and enter the amount you actually received.</p>
          <Field label="Amount received (₹)" error={received && !validReceived ? "Enter an amount like 48500 or 48500.50" : undefined}>
            <MoneyInput value={received} onChange={setReceived} />
          </Field>
          {validReceived && diff !== null && (
            <p className={`rounded p-2 text-sm font-medium ${hasDiff ? "bg-red-50 text-red-800" : "bg-green-50 text-green-800"}`}>
              Expected {formatInr(s.expected_amount)} · Received {formatInr(received)} · {hasDiff ? `${diff.startsWith("-") ? "Surplus" : "Shortfall"} ${formatInr(diff.replace("-", ""))}` : "Matches exactly"}
            </p>
          )}
          {hasDiff && <Field label="Reason for the difference (required)"><Input value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} /></Field>}
          {error && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <div className="flex gap-2">
            <PrimaryButton disabled={!validReceived || reasonMissing || approve.isPending} onClick={() => setDialog("approve")}>Approve</PrimaryButton>
            <button className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50" onClick={() => setDialog("reject")}>Reject…</button>
          </div>
        </div>
      )}
      {!canReview && error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div>
        <h2 className="mb-2 text-lg font-semibold">Included collections ({s.items?.length ?? 0})</h2>
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Receipt</th><th scope="col" className="p-3">Customer</th><th scope="col" className="p-3">Loan</th><th scope="col" className="p-3 text-right">Amount</th></tr></thead>
            <tbody>
              {s.items?.map((i) => (
                <tr key={i.id} className="border-b last:border-0">
                  <td className="p-3 font-mono text-xs">{i.receipt_number}</td><td className="p-3">{i.customer}</td><td className="p-3">{i.loan_number}</td><td className="p-3 text-right">{formatInr(i.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog open={dialog === "approve"} title="Approve this submission?"
        message={`Record ${formatInr(received)} as received${hasDiff ? ` with a ${diff!.startsWith("-") ? "surplus" : "shortfall"} of ${formatInr(diff!.replace("-", ""))}` : ""}. Approved submissions are final.`}
        confirmLabel="Approve" onCancel={() => setDialog(null)} onConfirm={() => approve.mutate()} />
      <ReasonDialog open={dialog === "reject"} title="Reject submission"
        description="The collections go back to the agent, who can submit them again."
        actionLabel="Reject" busy={reject.isPending} onCancel={() => setDialog(null)} onSubmit={(r) => reject.mutate(r)} />
    </section>
  );
}
