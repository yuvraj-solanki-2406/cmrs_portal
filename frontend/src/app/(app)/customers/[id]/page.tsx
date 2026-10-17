"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoanForm } from "@/components/lending/LoanForm";
import { useAuth } from "@/features/auth/AuthProvider";
import { assignAgent, getCustomer, listAgents, listLoans } from "@/features/lending/api";
import { ApiError } from "@/lib/apiClient";
import { formatInr } from "@/lib/money";
import { frequencyUnit } from "@/features/lending/types";
import { canManageLending } from "@/lib/roles";

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();
  const customer = useQuery({ queryKey: ["customer", id], queryFn: () => getCustomer(id) });
  const loans = useQuery({ queryKey: ["loans", { customer: id }], queryFn: () => listLoans({ customer: id }) });
  const canManage = !!user && canManageLending(user.role);
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => listAgents(), enabled: canManage });
  const [pendingAgent, setPendingAgent] = useState<string | null>(null);
  const [showLoanForm, setShowLoanForm] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const assign = useMutation({
    mutationFn: (agent: number | null) => assignAgent(Number(id), agent),
    onSuccess: () => { setPendingAgent(null); setAssignError(null); void qc.invalidateQueries({ queryKey: ["customer", id] }); void qc.invalidateQueries({ queryKey: ["customers"] }); },
    onError: (err) => { setPendingAgent(null); setAssignError(err instanceof ApiError ? err.userMessage : "Could not assign agent."); },
  });

  if (customer.isLoading) return <Spinner />;
  if (customer.isError) return <ErrorState error={customer.error} onRetry={() => void customer.refetch()} />;
  const c = customer.data!;
  const pendingName = agents.data?.find((a) => String(a.id) === pendingAgent);

  return (
    <section className="space-y-6">
      <div>
        <Link href="/customers" className="text-sm text-slate-500 underline">← Customers</Link>
        <h1 className="mt-1 text-2xl font-semibold">{c.full_name} <span className="font-mono text-sm text-slate-500">{c.customer_code}</span></h1>
      </div>

      <div className="grid gap-4 rounded-lg bg-white p-4 text-sm shadow-sm md:grid-cols-4">
        <div><p className="text-slate-500">Phone</p><p>{c.phone || "—"}</p></div>
        <div><p className="text-slate-500">Branch</p><p>{c.branch.code} · {c.branch.name}</p></div>
        <div><p className="text-slate-500">Status</p><StatusBadge status={c.is_active ? "ACTIVE" : "INACTIVE"} /></div>
        <div>
          <p className="text-slate-500">Assigned agent</p>
          {canManage ? (
            <select className={inputClass} value={c.assigned_agent?.id ?? ""} onChange={(e) => setPendingAgent(e.target.value)}>
              <option value="">Unassigned</option>
              {agents.data?.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
            </select>
          ) : <p>{c.assigned_agent?.full_name || c.assigned_agent?.username || "Unassigned"}</p>}
        </div>
        {c.address && <div className="md:col-span-4"><p className="text-slate-500">Address</p><p>{c.address}</p></div>}
      </div>
      {assignError && <p role="alert" className="text-sm text-red-700">{assignError}</p>}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Loans</h2>
        {canManage && c.is_active && (
          <button onClick={() => setShowLoanForm((s) => !s)} className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-1.5 text-sm text-white">{showLoanForm ? "Close" : "New loan"}</button>
        )}
      </div>
      {showLoanForm && canManage && <LoanForm customerId={c.id} />}
      {loans.isLoading && <Spinner />}
      {loans.isError && <ErrorState error={loans.error} />}
      {loans.data && loans.data.results.length === 0 && <EmptyState message="No loans yet." />}
      {loans.data && loans.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Loan</th><th scope="col" className="p-3 text-right">Total payable</th><th scope="col" className="p-3 text-right">Outstanding</th><th scope="col" className="p-3">Plan</th><th scope="col" className="p-3">Status</th></tr>
            </thead>
            <tbody>
              {loans.data.results.map((l) => (
                <tr key={l.id} className="border-b last:border-0">
                  <td className="p-3 font-medium"><Link className="underline" href={`/loans/${l.id}`}>{l.loan_number}</Link></td>
                  <td className="p-3 text-right">{formatInr(l.total_payable)}</td>
                  <td className="p-3 text-right">{formatInr(l.outstanding)}</td>
                  <td className="p-3">{l.installment_count} × {frequencyUnit(l.frequency)}</td>
                  <td className="p-3"><StatusBadge status={l.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog open={pendingAgent !== null} title="Change assigned agent"
        message={pendingName ? `Assign ${c.full_name} to ${pendingName.full_name || pendingName.username}?` : `Remove the agent assignment for ${c.full_name}?`}
        confirmLabel="Assign" onCancel={() => setPendingAgent(null)}
        onConfirm={() => assign.mutate(pendingAgent ? Number(pendingAgent) : null)} />
    </section>
  );
}
