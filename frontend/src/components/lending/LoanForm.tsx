"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Field, Input, MoneyInput, PrimaryButton, inputClass } from "@/components/ui/form";
import { InstallmentTable } from "@/components/lending/InstallmentTable";
import { createLoan } from "@/features/lending/api";
import { FREQUENCIES } from "@/features/lending/types";
import type { Installment, Loan } from "@/features/lending/types";
import { ApiError } from "@/lib/apiClient";
import { MONEY_PATTERN, formatInr } from "@/lib/money";

const money = z.string().regex(MONEY_PATTERN, "Enter an amount like 10000 or 10000.50");
const schema = z
  .object({
    principal: money,
    total_payable: money,
    installment_count: z.string().regex(/^\d+$/, "Whole number").refine((v) => +v >= 1 && +v <= 360, "1 to 360"),
    frequency: z.enum(["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY"]),
    start_date: z.string().min(1, "Required"),
  })
  // UX hint only (display-time comparison); the server enforces the real rule with Decimal.
  .refine((v) => !MONEY_PATTERN.test(v.principal) || !MONEY_PATTERN.test(v.total_payable) ||
    Math.round(Number(v.total_payable) * 100) >= Math.round(Number(v.principal) * 100),
    { path: ["total_payable"], message: "Total payable must be at least the principal" });
type FormValues = z.infer<typeof schema>;

export function LoanForm({ customerId, onCreated }: { customerId: number; onCreated?: (loan: Loan) => void }) {
  const qc = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [created, setCreated] = useState<(Loan & { installments: Installment[] }) | null>(null);
  const { register, control, handleSubmit, reset, setError, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { frequency: "MONTHLY", start_date: new Date().toISOString().slice(0, 10) },
  });

  const mutation = useMutation({
    mutationFn: (v: FormValues) =>
      createLoan({ customer: customerId, principal: v.principal, total_payable: v.total_payable,
        installment_count: Number(v.installment_count), frequency: v.frequency, start_date: v.start_date }),
    onSuccess: (loan) => {
      setCreated(loan); setServerError(null); reset();
      void qc.invalidateQueries({ queryKey: ["loans"] });
      onCreated?.(loan);
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setServerError(err.userMessage);
        for (const [f, msgs] of Object.entries(err.fieldErrors)) setError(f as keyof FormValues, { message: msgs.join(" ") });
      }
    },
  });

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit((v) => mutation.mutateAsync(v).catch(() => undefined))}
        className="grid gap-3 rounded-lg bg-white p-4 shadow-sm md:grid-cols-3">
        <Field label="Principal (₹)" error={errors.principal?.message}><Controller control={control} name="principal" render={({ field }) => <MoneyInput value={field.value ?? ""} onChange={field.onChange} onBlur={field.onBlur} />} /></Field>
        <Field label="Total payable (₹)" error={errors.total_payable?.message}><Controller control={control} name="total_payable" render={({ field }) => <MoneyInput value={field.value ?? ""} onChange={field.onChange} onBlur={field.onBlur} />} /></Field>
        <Field label="Installments" error={errors.installment_count?.message}><Input inputMode="numeric" {...register("installment_count")} /></Field>
        <Field label="Frequency" error={errors.frequency?.message}>
          <select className={inputClass} {...register("frequency")}>{FREQUENCIES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}</select>
        </Field>
        <Field label="Start date" error={errors.start_date?.message}><Input type="date" {...register("start_date")} /></Field>
        <div className="flex items-end"><PrimaryButton type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Creating…" : "Create loan"}</PrimaryButton></div>
        {serverError && <p role="alert" className="text-sm text-red-700 md:col-span-3">{serverError}</p>}
      </form>
      {created && (
        <div className="space-y-2">
          <p className="text-sm text-green-800">
            Loan {created.loan_number} created: {formatInr(created.total_payable)} over {created.installment_count} installments. Schedule (from server):
          </p>
          <InstallmentTable rows={created.installments} />
        </div>
      )}
    </div>
  );
}
