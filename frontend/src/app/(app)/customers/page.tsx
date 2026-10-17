"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { Field, Input, PrimaryButton, inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { createCustomer, listAgents, listCustomers } from "@/features/lending/api";
import { listBranches } from "@/features/admin/api";
import { ApiError } from "@/lib/apiClient";
import { canManageLending } from "@/lib/roles";

const schema = z.object({
  full_name: z.string().min(1, "Required"),
  phone: z.string().regex(/^[0-9]{10}$/, "Mobile number must be exactly 10 digits"),
  address: z.string(),
  branch: z.string(),
  assigned_agent: z.string(),
});
type FormValues = z.infer<typeof schema>;

export default function CustomersPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const isAdmin = user?.role === "ADMIN";
  const canManage = !!user && canManageLending(user.role);
  const filters = { page, search, assigned_agent: agentFilter };
  const customers = useQuery({ queryKey: ["customers", filters], queryFn: () => listCustomers(filters), placeholderData: keepPreviousData });
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => listAgents(), enabled: canManage });
  const branches = useQuery({ queryKey: ["branches"], queryFn: listBranches, enabled: isAdmin });

  const { register, handleSubmit, reset, control, setError, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema), defaultValues: { phone: "", address: "", branch: "", assigned_agent: "" },
  });
  const selectedBranch = useWatch({ control, name: "branch" });
  const create = useMutation({
    mutationFn: (v: FormValues) => createCustomer({
      full_name: v.full_name, phone: v.phone, address: v.address,
      branch: isAdmin ? Number(v.branch) || null : undefined,
      assigned_agent: v.assigned_agent ? Number(v.assigned_agent) : null,
    }),
    onSuccess: () => { reset(); setShowForm(false); setServerError(null); void qc.invalidateQueries({ queryKey: ["customers"] }); },
    onError: (err) => {
      if (err instanceof ApiError) {
        setServerError(err.userMessage);
        for (const [f, msgs] of Object.entries(err.fieldErrors)) setError(f as keyof FormValues, { message: msgs.join(" ") });
      }
    },
  });

  if (!user) return null;
  const agentOptions = (agents.data ?? []).filter((a) => !isAdmin || !selectedBranch || String(a.branch?.id) === selectedBranch);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{user.role === "AGENT" ? "My Customers" : "Customers"}</h1>
        {canManage && <PrimaryButton onClick={() => setShowForm((s) => !s)}>{showForm ? "Close" : "New customer"}</PrimaryButton>}
      </div>

      {showForm && canManage && (
        <form onSubmit={handleSubmit((v) => create.mutateAsync(v).catch(() => undefined))} className="grid gap-3 rounded-lg bg-white p-4 shadow-sm md:grid-cols-3">
          <Field label="Full name" error={errors.full_name?.message}><Input {...register("full_name")} /></Field>
          <Field label="Mobile number" error={errors.phone?.message}><Input {...register("phone")} inputMode="numeric" maxLength={10} placeholder="10 digits" /></Field>
          <Field label="Address" error={errors.address?.message}><Input {...register("address")} /></Field>
          {isAdmin && (
            <Field label="Branch" error={errors.branch?.message}>
              <select className={inputClass} {...register("branch")}>
                <option value="">Select…</option>
                {branches.data?.results.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
              </select>
            </Field>
          )}
          <Field label="Assigned agent" error={errors.assigned_agent?.message}>
            <select className={inputClass} {...register("assigned_agent")}>
              <option value="">Unassigned</option>
              {agentOptions.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
            </select>
          </Field>
          <div className="flex items-end"><PrimaryButton type="submit" disabled={create.isPending}>Create customer</PrimaryButton></div>
          {serverError && <p role="alert" className="text-sm text-red-700 md:col-span-3">{serverError}</p>}
        </form>
      )}

      <div className="flex flex-wrap gap-3">
        <input className={`${inputClass} max-w-xs`} placeholder="Search name, code or phone" value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        {canManage && (
          <select className={`${inputClass} max-w-xs`} value={agentFilter} onChange={(e) => { setAgentFilter(e.target.value); setPage(1); }}>
            <option value="">All agents</option>
            {agents.data?.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
          </select>
        )}
      </div>

      {customers.isLoading && <Spinner />}
      {customers.isError && <ErrorState error={customers.error} onRetry={() => void customers.refetch()} />}
      {customers.data && customers.data.results.length === 0 && <EmptyState message="No customers found." />}
      {customers.data && customers.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Code</th><th scope="col" className="p-3">Name</th><th scope="col" className="p-3">Phone</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Agent</th><th scope="col" className="p-3">Status</th></tr>
            </thead>
            <tbody>
              {customers.data.results.map((c) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="p-3 font-mono text-xs">{c.customer_code}</td>
                  <td className="p-3 font-medium"><Link className="underline" href={`/customers/${c.id}`}>{c.full_name}</Link></td>
                  <td className="p-3">{c.phone || "—"}</td>
                  <td className="p-3">{c.branch.code}</td>
                  <td className="p-3">{c.assigned_agent?.full_name || c.assigned_agent?.username || "Unassigned"}</td>
                  <td className="p-3"><StatusBadge status={c.is_active ? "ACTIVE" : "INACTIVE"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600">
            <span>{customers.data.count} customers</span>
            <div className="space-x-2">
              <button disabled={!customers.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button>
              <button disabled={!customers.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
