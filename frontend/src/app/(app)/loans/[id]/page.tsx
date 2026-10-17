"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { InstallmentTable } from "@/components/lending/InstallmentTable";
import { RepaymentHistory } from "@/components/collections/RepaymentHistory";
import { ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { loanRepayments } from "@/features/collections/api";
import { getInstallments, getLoan } from "@/features/lending/api";
import { formatInr } from "@/lib/money";

export default function LoanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const loan = useQuery({ queryKey: ["loan", id], queryFn: () => getLoan(id) });
  const { user } = useAuth();
  const repayments = useQuery({ queryKey: ["loan", id, "repayments"], queryFn: () => loanRepayments(id) });
  const installments = useQuery({ queryKey: ["loan", id, "installments"], queryFn: () => getInstallments(id) });

  if (loan.isLoading) return <Spinner />;
  if (loan.isError) return <ErrorState error={loan.error} onRetry={() => void loan.refetch()} />;
  const l = loan.data!;

  return (
    <section className="space-y-6">
      <div>
        <Link href={`/customers/${l.customer.id}`} className="text-sm text-slate-500 underline">← {l.customer.full_name}</Link>
        <div className="mt-1 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">{l.loan_number} <StatusBadge status={l.status} /></h1>
          {user?.role === "AGENT" && l.status === "ACTIVE" && (
            <Link href={`/collections/new?loan=${l.id}`} className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-2 text-sm text-white">Record repayment</Link>
          )}
        </div>
      </div>

      <div className="grid gap-4 rounded-lg bg-white p-4 text-sm shadow-sm md:grid-cols-4">
        <div><p className="text-slate-500">Principal</p><p className="text-lg font-semibold">{formatInr(l.principal)}</p></div>
        <div><p className="text-slate-500">Total payable</p><p className="text-lg font-semibold">{formatInr(l.total_payable)}</p></div>
        <div><p className="text-slate-500">Paid</p><p className="text-lg font-semibold">{formatInr(l.paid)}</p></div>
        <div><p className="text-slate-500">Outstanding</p><p className="text-lg font-semibold text-amber-700">{formatInr(l.outstanding)}</p></div>
      </div>

      <div>
        <h2 className="mb-2 text-lg font-semibold">Repayment schedule</h2>
        {installments.isLoading && <Spinner />}
        {installments.isError && <ErrorState error={installments.error} />}
        {installments.data && <InstallmentTable rows={installments.data} />}
      </div>

      <div>
        <h2 className="mb-2 text-lg font-semibold">Repayment history</h2>
        {repayments.isLoading && <Spinner />}
        {repayments.isError && <ErrorState error={repayments.error} />}
        {repayments.data && <RepaymentHistory rows={repayments.data} />}
      </div>
    </section>
  );
}
