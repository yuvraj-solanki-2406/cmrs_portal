"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field, Input, PrimaryButton } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { pendingCollections, submitCash } from "@/features/cash/api";
import { ApiError } from "@/lib/apiClient";
import { formatInr, sumMoney } from "@/lib/money";

export default function CashHoldingPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const pending = useQuery({ queryKey: ["pending-collections"], queryFn: pendingCollections });
  const [unchecked, setUnchecked] = useState<Set<number>>(new Set());
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One Idempotency-Key per logical attempt (same ids + note); renewed when the selection changes.
  const attempt = useRef<{ key: string; signature: string } | null>(null);

  if (pending.isLoading) return <Spinner />;
  if (pending.isError) return <ErrorState error={pending.error} onRetry={() => void pending.refetch()} />;
  const data = pending.data!;
  const selected = data.collections.filter((c) => !unchecked.has(c.id));
  const total = sumMoney(selected.map((c) => c.amount));

  const toggle = (id: number) => setUnchecked((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const submit = async () => {
    setConfirming(false); setError(null); setBusy(true);
    const ids = selected.map((c) => c.id).sort((a, b) => a - b);
    const signature = `${ids.join(",")}|${note.trim()}`;
    if (!attempt.current || attempt.current.signature !== signature) attempt.current = { key: crypto.randomUUID(), signature };
    try {
      const sub = await submitCash(ids, note, attempt.current.key);
      attempt.current = null;
      void qc.invalidateQueries({ queryKey: ["pending-collections"] });
      void qc.invalidateQueries({ queryKey: ["submissions"] });
      router.push(`/submissions/${sub.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : "Network error. You can safely retry: the same request will not be submitted twice.");
      void qc.invalidateQueries({ queryKey: ["pending-collections"] });
    } finally { setBusy(false); }
  };

  return (
    <section className="space-y-5">
      <h1 className="text-2xl font-semibold">Cash Holding</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Cash I am holding</p><p className="text-2xl font-semibold">{formatInr(data.total)}</p><p className="text-xs text-slate-500">{data.count} collections</p></div>
        <div className="rounded-lg bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Submitted, awaiting branch</p><p className="text-2xl font-semibold">{formatInr(data.in_transit)}</p></div>
        <div className="rounded-lg bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Open shortfall against me</p><p className={`text-2xl font-semibold ${data.open_shortfall !== "0.00" ? "text-red-700" : ""}`}>{formatInr(data.open_shortfall)}</p></div>
      </div>

      {data.collections.length === 0 ? (
        <EmptyState message="No cash to submit. Record repayments from Today, then submit them here." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-slate-50 text-slate-600">
                <tr><th scope="col" className="w-10 p-3"><span className="sr-only">Select</span></th><th scope="col" className="p-3">Receipt</th><th scope="col" className="p-3">Customer</th><th scope="col" className="p-3">Date</th><th scope="col" className="p-3 text-right">Amount</th></tr>
              </thead>
              <tbody>
                {data.collections.map((c) => (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="p-3"><input type="checkbox" aria-label={`Include ${c.receipt_number}`} checked={!unchecked.has(c.id)} onChange={() => toggle(c.id)} /></td>
                    <td className="p-3 font-mono text-xs">{c.receipt_number}</td>
                    <td className="p-3">{c.customer.full_name}</td>
                    <td className="p-3">{new Date(c.collected_at).toLocaleString("en-IN")}</td>
                    <td className="p-3 text-right">{formatInr(c.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="max-w-md space-y-3 rounded-lg bg-white p-4 shadow-sm">
            <p className="text-sm">Selected: <b>{selected.length}</b> collections, total <b>{formatInr(total)}</b></p>
            <Field label="Note for the branch manager (optional)"><Input value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} /></Field>
            {error && <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
            <PrimaryButton disabled={busy || selected.length === 0} onClick={() => setConfirming(true)}>{busy ? "Submitting…" : "Submit cash to branch"}</PrimaryButton>
            <p className="text-xs text-slate-500">The branch manager will count the cash and approve or reject. See <Link className="underline" href="/submissions">My Submissions</Link>.</p>
          </div>
        </>
      )}
      <ConfirmDialog open={confirming} title="Submit cash to branch"
        message={`Hand over ${formatInr(total)} (${selected.length} collections) to the branch? The manager will verify the amount you physically give them.`}
        confirmLabel="Submit" onCancel={() => setConfirming(false)} onConfirm={() => void submit()} />
    </section>
  );
}
