"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Field, Input, PrimaryButton } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { createBranch, listBranches } from "@/features/admin/api";
import { ApiError } from "@/lib/apiClient";

const schema = z.object({
  code: z.string().min(2, "At least 2 characters").max(20),
  name: z.string().min(1, "Required"),
});
type FormValues = z.infer<typeof schema>;

export default function BranchesPage() {
  const qc = useQueryClient();
  const branches = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, reset, setError, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const create = useMutation({
    mutationFn: createBranch,
    onSuccess: () => { reset(); setServerError(null); void qc.invalidateQueries({ queryKey: ["branches"] }); },
    onError: (err) => {
      if (err instanceof ApiError) {
        setServerError(err.userMessage);
        for (const [field, msgs] of Object.entries(err.fieldErrors)) setError(field as keyof FormValues, { message: msgs.join(" ") });
      }
    },
  });

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Branches</h1>
      <form onSubmit={handleSubmit((v) => create.mutateAsync(v).catch(() => undefined))} className="grid gap-3 rounded-lg bg-white p-4 shadow-sm md:grid-cols-3">
        <Field label="Code" error={errors.code?.message}><Input {...register("code")} /></Field>
        <Field label="Name" error={errors.name?.message}><Input {...register("name")} /></Field>
        <div className="flex items-end"><PrimaryButton type="submit" disabled={isSubmitting}>Add branch</PrimaryButton></div>
        {serverError && <p role="alert" className="md:col-span-3 text-sm text-red-700">{serverError}</p>}
      </form>
      {branches.isLoading && <Spinner />}
      {branches.isError && <ErrorState error={branches.error} onRetry={() => void branches.refetch()} />}
      {branches.data && branches.data.results.length === 0 && <EmptyState message="No branches yet." />}
      {branches.data && branches.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Code</th><th scope="col" className="p-3">Name</th><th scope="col" className="p-3">Status</th></tr></thead>
            <tbody>
              {branches.data.results.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="p-3 font-medium">{b.code}</td><td className="p-3">{b.name}</td>
                  <td className="p-3"><StatusBadge status={b.is_active ? "ACTIVE" : "INACTIVE"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
