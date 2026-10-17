"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { Field, Input, PrimaryButton, inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { createUser, listBranches, listUsers, setUserActive } from "@/features/admin/api";
import { ApiError } from "@/lib/apiClient";
import { ROLE_LABELS, type RoleCode } from "@/lib/roles";

const ROLES = Object.keys(ROLE_LABELS) as RoleCode[];
const BRANCH_BOUND: RoleCode[] = ["AGENT", "BRANCH_MANAGER"];

const schema = z
  .object({
    username: z.string().min(3, "At least 3 characters"),
    password: z.string().min(8, "At least 8 characters"),
    full_name: z.string().min(1, "Required"),
    role: z.enum(["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"]),
    branch: z.string(),
  })
  .refine((v) => !BRANCH_BOUND.includes(v.role) || v.branch !== "", { path: ["branch"], message: "Branch is required for this role" });
type FormValues = z.infer<typeof schema>;

export default function UsersPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const users = useQuery({ queryKey: ["users", page], queryFn: () => listUsers(page) });
  const branches = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, reset, control, setError, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { role: "AGENT", branch: "" } });
  const role = useWatch({ control, name: "role" });

  const create = useMutation({
    mutationFn: (v: FormValues) =>
      createUser({ ...v, branch: BRANCH_BOUND.includes(v.role) ? Number(v.branch) : null }),
    onSuccess: () => { reset(); setServerError(null); void qc.invalidateQueries({ queryKey: ["users"] }); },
    onError: (err) => {
      if (err instanceof ApiError) {
        setServerError(err.userMessage);
        for (const [field, msgs] of Object.entries(err.fieldErrors)) setError(field as keyof FormValues, { message: msgs.join(" ") });
      }
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => setUserActive(id, active),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Users</h1>

      <form onSubmit={handleSubmit((v) => create.mutateAsync(v).catch(() => undefined))} className="grid gap-3 rounded-lg bg-white p-4 shadow-sm md:grid-cols-3">
        <Field label="Username" error={errors.username?.message}><Input {...register("username")} /></Field>
        <Field label="Full name" error={errors.full_name?.message}><Input {...register("full_name")} /></Field>
        <Field label="Password" error={errors.password?.message}><Input type="password" autoComplete="new-password" {...register("password")} /></Field>
        <Field label="Role" error={errors.role?.message}>
          <select className={inputClass} {...register("role")}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
        </Field>
        <Field label="Branch" error={errors.branch?.message}>
          <select className={inputClass} disabled={!BRANCH_BOUND.includes(role)} {...register("branch")}>
            <option value="">—</option>
            {branches.data?.results.map((b) => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}
          </select>
        </Field>
        <div className="flex items-end"><PrimaryButton type="submit" disabled={isSubmitting}>Create user</PrimaryButton></div>
        {serverError && <p role="alert" className="md:col-span-3 text-sm text-red-700">{serverError}</p>}
      </form>

      {users.isLoading && <Spinner />}
      {users.isError && <ErrorState error={users.error} onRetry={() => void users.refetch()} />}
      {users.data && users.data.results.length === 0 && <EmptyState message="No users yet." />}
      {users.data && users.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr><th scope="col" className="p-3">Username</th><th scope="col" className="p-3">Name</th><th scope="col" className="p-3">Role</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Status</th><th scope="col" className="p-3"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {users.data.results.map((u) => (
                <tr key={u.id} className="border-b last:border-0">
                  <td className="p-3 font-medium">{u.username}</td>
                  <td className="p-3">{u.full_name}</td>
                  <td className="p-3">{ROLE_LABELS[u.role]}</td>
                  <td className="p-3">{u.branch?.code ?? "—"}</td>
                  <td className="p-3"><StatusBadge status={u.is_active ? "ACTIVE" : "INACTIVE"} /></td>
                  <td className="p-3 text-right">
                    <button className="text-xs text-slate-600 underline" onClick={() => toggle.mutate({ id: u.id, active: !u.is_active })}>
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600">
            <span>{users.data.count} users</span>
            <div className="space-x-2">
              <button disabled={!users.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button>
              <button disabled={!users.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
