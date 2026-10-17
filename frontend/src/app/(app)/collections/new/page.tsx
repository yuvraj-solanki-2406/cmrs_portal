"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field, Input, MoneyInput, PrimaryButton } from "@/components/ui/form";
import { ErrorState, Spinner } from "@/components/ui/states";
import { recordRepayment } from "@/features/collections/api";
import type { Collection } from "@/features/collections/types";
import { getLoan } from "@/features/lending/api";
import { ApiError } from "@/lib/apiClient";
import { MONEY_PATTERN, formatInr } from "@/lib/money";

function RecordForm() {
  const loanId = useSearchParams().get("loan") ?? "";
  const qc = useQueryClient();
  const loan = useQuery({ queryKey: ["loan", loanId], queryFn: () => getLoan(loanId), enabled: !!loanId });
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [maxAllowed, setMaxAllowed] = useState<string | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<Collection | null>(null);
  // One Idempotency-Key per logical attempt: reused on retries of the same request, renewed when the
  // payload changes (a different payload under an old key would be rejected with 422) or after success.
  const attempt = useRef<{ key: string; signature: string } | null>(null);

  const submit = async (confirmDuplicate = false) => {
    setError(null); setFieldError(null); setMaxAllowed(null);
    if (!MONEY_PATTERN.test(amount) || Number(amount) <= 0) { setFieldError("Enter an amount like 2500 or 2500.50"); return; }
    const signature = `${amount}|${note.trim()}`;
    if (!attempt.current || attempt.current.signature !== signature) attempt.current = { key: crypto.randomUUID(), signature };
    setBusy(true);
    try {
      const result = await recordRepayment({ loan: Number(loanId), amount, note, confirm_duplicate: confirmDuplicate || undefined }, attempt.current.key);
      setReceipt(result);
      attempt.current = null;
      void qc.invalidateQueries({ queryKey: ["loan"] });
      void qc.invalidateQueries({ queryKey: ["loans"] });
      void qc.invalidateQueries({ queryKey: ["collections"] });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.body.code === "POSSIBLE_DUPLICATE") setNeedsConfirm(true);
        else if (err.body.code === "OVER_COLLECTION") { setMaxAllowed(String(err.body.details?.max_allowed ?? "")); setError(err.userMessage); }
        else setError(err.userMessage);
      } else setError("Network error. You can safely retry: the same request will not be recorded twice.");
    } finally { setBusy(false); }
  };

  if (!loanId) return <p className="text-sm">Choose a loan from <Link className="underline" href="/today">Today</Link> or a customer page.</p>;
  if (loan.isLoading) return <Spinner />;
  if (loan.isError) return <ErrorState error={loan.error} />;
  const l = loan.data!;

  if (receipt) {
    return (
      <div className="max-w-md space-y-3 rounded-lg border border-green-200 bg-green-50 p-5">
        <h2 className="text-lg font-semibold text-green-900">Repayment recorded</h2>
        <dl className="grid grid-cols-2 gap-1 text-sm">
          <dt className="text-slate-600">Receipt</dt><dd className="font-mono">{receipt.receipt_number}</dd>
          <dt className="text-slate-600">Customer</dt><dd>{receipt.customer.full_name}</dd>
          <dt className="text-slate-600">Loan</dt><dd>{receipt.loan.loan_number}</dd>
          <dt className="text-slate-600">Amount</dt><dd className="font-semibold">{formatInr(receipt.amount)}</dd>
          <dt className="text-slate-600">Time</dt><dd>{new Date(receipt.collected_at).toLocaleString("en-IN")}</dd>
        </dl>
        <p className="text-xs text-slate-600">The cash is still with you until you submit it to the branch.</p>
        <div className="flex gap-2">
          <button className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-1.5 text-sm text-white" onClick={() => { setReceipt(null); setAmount(""); setNote(""); }}>Record another</button>
          <Link href="/today" className="rounded border border-slate-300 px-3 py-1.5 text-sm">Back to Today</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md space-y-4">
      <div className="rounded-lg bg-white p-4 text-sm shadow-sm">
        <p className="font-medium">{l.customer.full_name} · {l.loan_number}</p>
        <p className="text-slate-600">Outstanding {formatInr(l.outstanding)}{l.due_now && l.due_now !== "0.00" ? ` · due now ${formatInr(l.due_now)}` : ""}</p>
      </div>
      <form className="space-y-3 rounded-lg bg-white p-4 shadow-sm" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <Field label="Amount received (₹)" error={fieldError ?? undefined}>
          <MoneyInput value={amount} onChange={setAmount} autoFocus />
        </Field>
        <Field label="Note (optional)"><Input value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} /></Field>
        {error && (
          <div role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">
            {error}
            {maxAllowed && <button type="button" className="ml-2 underline" onClick={() => { setAmount(maxAllowed); setError(null); setMaxAllowed(null); }}>Use {formatInr(maxAllowed)}</button>}
          </div>
        )}
        <PrimaryButton type="submit" disabled={busy || l.status !== "ACTIVE"}>{busy ? "Recording…" : "Record repayment"}</PrimaryButton>
        {l.status !== "ACTIVE" && <p className="text-sm text-slate-600">This loan is closed.</p>}
      </form>
      <ConfirmDialog open={needsConfirm} title="Possible duplicate"
        message={`${formatInr(amount)} was already recorded for this loan in the last 10 minutes. Record it again?`}
        confirmLabel="Record again" onCancel={() => setNeedsConfirm(false)}
        onConfirm={() => { setNeedsConfirm(false); void submit(true); }} />
    </div>
  );
}

export default function NewCollectionPage() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Record repayment</h1>
      <Suspense fallback={<Spinner />}><RecordForm /></Suspense>
    </section>
  );
}
