"use client";

import { useQuery } from "@tanstack/react-query";

import { inputClass } from "@/components/ui/form";
import { listBranches } from "@/features/admin/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { listAgents } from "@/features/lending/api";

export type FilterValues = { date_from: string; date_to: string; branch: string; agent: string; stage: string };

export const STAGE_OPTIONS = [
  { value: "COLLECTED", label: "Collected" }, { value: "HELD", label: "Held by agents" },
  { value: "IN_TRANSIT", label: "In transit" }, { value: "BRANCH_RECEIVED", label: "Received at branch" },
  { value: "DEPOSITED", label: "Deposited" }, { value: "SETTLED", label: "Settled" },
];

/** Date range, branch, agent and (optionally) pipeline stage. Backend scope always wins over these controls. */
export function FilterBar({ values, onChange, showStage = false }: { values: FilterValues; onChange: (p: Partial<FilterValues>) => void; showStage?: boolean }) {
  const { user } = useAuth();
  const role = user?.role;
  const canPickBranch = role === "FINANCE" || role === "ADMIN";
  const canPickAgent = role === "BRANCH_MANAGER" || role === "FINANCE" || role === "ADMIN";
  const branches = useQuery({ queryKey: ["branches"], queryFn: listBranches, enabled: canPickBranch });
  const agents = useQuery({ queryKey: ["agents", values.branch], queryFn: () => listAgents(values.branch ? Number(values.branch) : undefined), enabled: canPickAgent });
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg bg-white p-3 shadow-sm">
      <label className="text-sm">From<input type="date" className={`${inputClass} mt-1`} value={values.date_from} onChange={(e) => onChange({ date_from: e.target.value })} /></label>
      <label className="text-sm">To<input type="date" className={`${inputClass} mt-1`} value={values.date_to} onChange={(e) => onChange({ date_to: e.target.value })} /></label>
      {canPickBranch && (
        <label className="text-sm">Branch
          <select className={`${inputClass} mt-1`} value={values.branch} onChange={(e) => onChange({ branch: e.target.value, agent: "" })}>
            <option value="">All branches</option>{branches.data?.results.map((b) => <option key={b.id} value={b.id}>{b.code}</option>)}
          </select>
        </label>
      )}
      {canPickAgent && (
        <label className="text-sm">Agent
          <select className={`${inputClass} mt-1`} value={values.agent} onChange={(e) => onChange({ agent: e.target.value })}>
            <option value="">All agents</option>{agents.data?.map((a) => <option key={a.id} value={a.id}>{a.full_name || a.username}</option>)}
          </select>
        </label>
      )}
      {showStage && (
        <label className="text-sm">Status (stage)
          <select className={`${inputClass} mt-1`} value={values.stage} onChange={(e) => onChange({ stage: e.target.value })}>
            <option value="">Overview</option>{STAGE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
      )}
      <button className="border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium hover:bg-secondary" onClick={() => onChange({ date_from: "", date_to: "", branch: "", agent: "", stage: "" })}>Reset</button>
    </div>
  );
}

export const toQuery = (v: FilterValues) => ({
  date_from: v.date_from || undefined, date_to: v.date_to || undefined, branch: v.branch || undefined,
  agent: v.agent || undefined, stage: v.stage || undefined,
});
