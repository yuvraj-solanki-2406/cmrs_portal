"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field, Input, MoneyInput, PrimaryButton, inputClass } from "@/components/ui/form";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { eligibleSubmissions, recordDeposit } from "@/features/treasury/api";
import { BANKS } from "@/features/treasury/types";
import { ApiError } from "@/lib/apiClient";
import { MONEY_PATTERN, formatInr, subtractMoney, sumMoney } from "@/lib/money";

export default function NewDepositPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const eligible = useQuery({ queryKey: ["eligible-submissions"], queryFn: eligibleSubmissions });
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [amount, setAmount] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);
  const [bank, setBank] = useState("HDFC");
  const today = new Date().toLocaleDateString("en-CA");
  const [date, setDate] = useState(today);
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  if (eligible.isLoading) return <Spinner />;
  if (eligible.isError) return <ErrorState error={eligible.error} onRetry={() => void eligible.refetch()} />;
  const rows = eligible.data!;
  const chosen = rows.filter((r) => picked.has(r.id));
  const reconciled = sumMoney(chosen.map((r) => r.received_amount));
  // Until the user types their own amount, it follows the reconciled total of the selection.
  const effectiveAmount = amountTouched ? amount : chosen.length ? reconciled : "";
  const validAmount = MONEY_PATTERN.test(effectiveAmount) && effectiveAmount !== "0" && effectiveAmount !== "0.00";
  const variance = validAmount ? subtractMoney(effectiveAmount, reconciled) : null; // deposit − reconciled
  const hasVariance = variance !== null && variance !== "0.00";

  const toggle = (id: number) => setPicked((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const canSubmit = chosen.length > 0 && validAmount && reference.trim() !== "" && (!hasVariance || note.trim() !== "");

  const submit = async () => {
    setConfirming(false); setBusy(true); setError(null); setFieldErrors({});
    try {
      const dep = await recordDeposit({ submission_ids: chosen.map((r) => r.id), bank_name: bank, amount: effectiveAmount,
        deposit_date: date, reference_number: reference.trim(), variance_note: note });
      void qc.invalidateQueries({ queryKey: ["deposits"] });
      void qc.invalidateQueries({ queryKey: ["eligible-submissions"] });
      router.push(`/deposits/${dep.id}`);
    } catch (err) {
      if (err instanceof ApiError) { setError(err.userMessage); setFieldErrors(err.fieldErrors); void qc.invalidateQueries({ queryKey: ["eligible-submissions"] }); }
      else setError("Network error. Check Deposits before retrying so the same deposit is not recorded twice.");
    } finally { setBusy(false); }
  };

  return (
    <section className="space-y-5">
      <div>
        <Link href="/deposits" className="text-sm text-slate-500 underline">← Deposits</Link>
        <h1 className="mt-1 text-2xl font-semibold">New bank deposit</h1>
        <p className="text-sm text-slate-600">Select the approved cash you banked. A deposit covers whole submissions.</p>
      </div>

      {rows.length === 0 ? <EmptyState message="No approved submissions are waiting to be deposited." /> : (
        <>
          <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-slate-50 text-slate-600">
                <tr><th scope="col" className="w-10 p-3"><span className="sr-only">Select</span></th><th scope="col" className="p-3">Submission</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3 text-right">Expected</th><th scope="col" className="p-3 text-right">Received (reconciled)</th><th scope="col" className="p-3 text-right">Difference</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b last:border-0">
                    <td className="p-3"><input type="checkbox" aria-label={`Include ${r.reference_no}`} checked={picked.has(r.id)} onChange={() => toggle(r.id)} /></td>
                    <td className="p-3 font-mono text-xs">{r.reference_no}</td><td className="p-3">{r.agent}</td>
                    <td className="p-3 text-right">{formatInr(r.expected_amount)}</td><td className="p-3 text-right">{formatInr(r.received_amount)}</td>
                    <td className={`p-3 text-right ${r.discrepancy_amount !== "0.00" ? "font-medium text-red-700" : ""}`}>{formatInr(r.discrepancy_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form className="grid max-w-3xl gap-3 rounded-lg bg-white p-4 shadow-sm md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (canSubmit) setConfirming(true); }}>
            <p className="text-sm md:col-span-2">Selected {chosen.length} submission(s). Reconciled cash: <b>{formatInr(reconciled)}</b></p>
            <Field label="Amount deposited (₹)" error={fieldErrors.amount?.join(" ")}>
              <MoneyInput value={effectiveAmount} onChange={(v) => { setAmount(v); setAmountTouched(true); }} />
            </Field>
            <Field label="Bank">
              <select className={inputClass} value={bank} onChange={(e) => setBank(e.target.value)}>{BANKS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}</select>
            </Field>
            <Field label="Deposit date" error={fieldErrors.deposit_date?.join(" ")}><Input type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
            <Field label="Transaction / reference number" error={fieldErrors.reference_number?.join(" ")}><Input value={reference} maxLength={60} onChange={(e) => setReference(e.target.value)} /></Field>
            {validAmount && chosen.length > 0 && (
              <p className={`rounded p-2 text-sm font-medium md:col-span-2 ${hasVariance ? "bg-red-50 text-red-800" : "bg-green-50 text-green-800"}`}>
                Reconciled {formatInr(reconciled)} · Deposited {formatInr(effectiveAmount)} · {hasVariance ? `Variance ${formatInr(variance!)}` : "Matches exactly"}
              </p>
            )}
            {hasVariance && <div className="md:col-span-2"><Field label="Reason for the difference (required)" error={fieldErrors.variance_note?.join(" ")}><Input value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} /></Field></div>}
            {error && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700 md:col-span-2">{error}</p>}
            <div className="md:col-span-2"><PrimaryButton type="submit" disabled={!canSubmit || busy}>{busy ? "Recording…" : "Record deposit"}</PrimaryButton></div>
          </form>
        </>
      )}
      <ConfirmDialog open={confirming} title="Record bank deposit"
        message={`Record ${formatInr(effectiveAmount)} deposited at ${bank} (ref ${reference.trim()}) against ${chosen.length} submission(s)? Deposits cannot be edited afterwards.`}
        confirmLabel="Record deposit" onCancel={() => setConfirming(false)} onConfirm={() => void submit()} />
    </section>
  );
}
