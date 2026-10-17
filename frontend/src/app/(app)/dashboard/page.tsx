"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Suspense } from "react";

import { CsvButton } from "@/components/reporting/CsvButton";
import { FilterBar, STAGE_OPTIONS, toQuery, type FilterValues } from "@/components/reporting/FilterBar";
import { useUrlFilters } from "@/components/reporting/useUrlFilters";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/features/auth/AuthProvider";
import { getBranchSummary, getStageRecords, getSummary } from "@/features/reporting/api";
import type { Metrics, StageRow } from "@/features/reporting/types";
import { formatInr } from "@/lib/money";
import { ROLE_LABELS } from "@/lib/roles";

const monthStart = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1).toLocaleDateString("en-CA"); };
const today = () => new Date().toLocaleDateString("en-CA");

const TILES: { key: keyof Metrics; label: string; help: string; tone?: string }[] = [
  { key: "expected", label: "Expected collections", help: "Sum of installments falling due in the selected dates." },
  { key: "collected", label: "Total collected", help: "Valid repayments recorded by agents in the selected dates." },
  { key: "held_by_agents", label: "Cash held by agents", help: "Valid collections not yet in any live cash submission." },
  { key: "in_transit", label: "Submitted, awaiting branch", help: "Cash submitted by agents and waiting for the branch manager to count it." },
  { key: "received_at_branch", label: "Received at branches", help: "Counted amount of approved submissions (actual cash, not the collection total)." },
  { key: "deposited", label: "Bank deposits", help: "Sum of recorded bank deposits (for an agent view: that agent's cash that has been banked)." },
  { key: "settled", label: "Settled amount", help: "Amount the bank actually credited, per confirmed settlements." },
  { key: "outstanding", label: "Outstanding (loans)", help: "Total payable minus repayments on active loans, as of now." },
  { key: "discrepancy_total", label: "Reconciliation discrepancies", help: "Absolute sum of shortfalls and surpluses found at branch counting.", tone: "text-red-700" },
];

function Tile({ label, help, value, sub, tone }: { label: string; help: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-white p-4 shadow-sm" title={help}>
      <p className="text-sm text-slate-500">{label} <span aria-hidden className="cursor-help text-xs text-slate-400">ⓘ</span></p>
      <p className={`text-2xl font-semibold ${tone ?? ""}`}>{formatInr(value)}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function StageTable({ rows }: { rows: StageRow[] }) {
  const href = (r: StageRow) => (r.kind === "collection" ? `/trace/collection/${r.id}` : r.kind === "submission" ? `/submissions/${r.id}` : `/deposits/${r.id}`);
  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">Reference</th><th scope="col" className="p-3">Date</th><th scope="col" className="p-3">Branch</th><th scope="col" className="p-3">Agent / party</th><th scope="col" className="p-3 text-right">Amount</th><th scope="col" className="p-3">Status</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.kind}-${r.id}`} className="border-b last:border-0">
              <td className="p-3 font-mono text-xs"><Link className="underline" href={href(r)}>{r.reference}</Link></td>
              <td className="p-3">{new Date(r.date).toLocaleDateString("en-IN")}</td><td className="p-3">{r.branch}</td>
              <td className="p-3">{r.agent || r.party}{r.agent && r.party ? ` · ${r.party}` : ""}</td>
              <td className="p-3 text-right">{formatInr(r.amount)}</td><td className="p-3"><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Dashboard() {
  const { user } = useAuth();
  const [values, setValues] = useUrlFilters<FilterValues>({ date_from: monthStart(), date_to: today(), branch: "", agent: "", stage: "" });
  const query = toQuery(values);
  const summary = useQuery({ queryKey: ["dashboard", "summary", query], queryFn: () => getSummary(query) });
  const records = useQuery({ queryKey: ["dashboard", "records", query], queryFn: () => getStageRecords(query), enabled: !!values.stage });
  const oversight = user?.role === "BRANCH_MANAGER" || user?.role === "FINANCE" || user?.role === "ADMIN";
  const branches = useQuery({ queryKey: ["dashboard", "branches", { ...query, stage: undefined }], queryFn: () => getBranchSummary(query), enabled: oversight });
  if (!user) return null;
  const m = summary.data?.metrics;
  const max = Math.max(1, ...(summary.data?.funnel.map((f) => Number(f.amount)) ?? [1])); // bar widths only, not accounting

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-slate-600">{ROLE_LABELS[user.role]}{user.branch ? ` · ${user.branch.name}` : " · all branches"}</p>
        </div>
        {oversight && <div className="flex gap-2 text-sm"><Link className="underline" href="/reports/discrepancies">Discrepancy report</Link><span>·</span><Link className="underline" href="/reports/mismatches">Deposit &amp; settlement mismatches</Link></div>}
      </div>
      <FilterBar values={values} onChange={setValues} showStage />

      {summary.isLoading && <Spinner />}
      {summary.isError && <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />}
      {m && summary.data && (
        <>
          {summary.data.attribution === "submission" && <p className="rounded bg-secondary p-2 text-xs text-ink">Showing figures for the selected agent. Deposited and settled amounts are that agent&apos;s cash that has been banked/settled (deposits themselves are branch-level).</p>}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TILES.map((t) => (
              <Tile key={t.key} label={t.label} help={t.help} value={String(m[t.key])} tone={t.tone}
                sub={t.key === "discrepancy_total" ? `${m.discrepancy_count} cases · shortfall ${formatInr(m.shortfall_total)} · surplus ${formatInr(m.surplus_total)}`
                  : t.key === "settled" && m.delayed_settlements !== null ? `${m.delayed_settlements} delayed · ${formatInr(m.pending_settlement_amount)} pending`
                  : t.key === "deposited" && summary.data.attribution === "deposit" ? `Deposit variances: ${formatInr(m.deposit_variance_total)} (${m.deposit_variance_count}) · settlement variances: ${formatInr(m.settlement_variance_total)} (${m.settlement_variance_count})` : undefined} />
            ))}
          </div>

          <div className="rounded-lg bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Cash pipeline</h2>
            <div className="space-y-2">
              {summary.data.funnel.map((f) => (
                <div key={f.stage} className="flex items-center gap-3 text-sm">
                  <span className="w-36 shrink-0 text-slate-600">{f.label}</span>
                  <div className="h-5 flex-1 rounded bg-primary"><div className="h-5 rounded bg-tertiary" style={{ width: `${(Number(f.amount) / max) * 100}%` }} /></div>
                  <span className="w-32 shrink-0 text-right font-medium">{formatInr(f.amount)}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">Branch received, deposited and settled use actual counted/banked cash, so they can be lower than Collected when there are discrepancies.</p>
          </div>
        </>
      )}

      {values.stage && (
        <div className="space-y-2">
          <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Records: {STAGE_OPTIONS.find((s) => s.value === values.stage)?.label}</h2>
            {["COLLECTED", "HELD"].includes(values.stage) && <CsvButton path="/export/collections.csv" query={{ date_from: query.date_from, date_to: query.date_to, agent: query.agent, branch: query.branch }} filename="collections.csv" />}</div>
          {records.isLoading && <Spinner />}
          {records.isError && <ErrorState error={records.error} />}
          {records.data && records.data.rows.length === 0 && <EmptyState message="No records for this stage and filters." />}
          {records.data && records.data.rows.length > 0 && <><StageTable rows={records.data.rows} />{records.data.truncated && <p className="text-xs text-slate-500">Showing the latest {records.data.rows.length} of {records.data.total}.</p>}</>}
        </div>
      )}

      {oversight && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Branch &amp; agent summary</h2>
          {branches.isLoading && <Spinner />}
          {branches.isError && <ErrorState error={branches.error} />}
          {branches.data && branches.data.branches.length === 0 && <EmptyState message="No branches in scope." />}
          {branches.data?.branches.map((b) => (
            <div key={b.branch.id} className="overflow-x-auto rounded-lg bg-white shadow-sm">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-slate-50 text-slate-600">
                  <tr><th scope="col" className="p-3">{b.branch.code} · {b.branch.name}</th><th scope="col" className="p-3 text-right">Collected</th><th scope="col" className="p-3 text-right">Held</th><th scope="col" className="p-3 text-right">In transit</th><th scope="col" className="p-3 text-right">Received</th><th scope="col" className="p-3 text-right">Shortfall</th><th scope="col" className="p-3 text-right">Outstanding</th></tr>
                </thead>
                <tbody>
                  <tr className="border-b bg-primary/60 font-medium">
                    <td className="p-3">Branch total{b.delayed_settlements ? <span className="ml-2"><StatusBadge status="DELAYED" /></span> : null}</td>
                    <td className="p-3 text-right">{formatInr(b.collected)}</td><td className="p-3 text-right">{formatInr(b.held_by_agents)}</td><td className="p-3 text-right">{formatInr(b.in_transit)}</td>
                    <td className="p-3 text-right">{formatInr(b.received_at_branch)}</td><td className="p-3 text-right">{formatInr(b.discrepancy_total)}</td><td className="p-3 text-right">{formatInr(b.outstanding)}</td>
                  </tr>
                  {b.agents.map((a) => (
                    <tr key={a.agent.id} className="border-b last:border-0">
                      <td className="p-3 pl-6">{a.agent.full_name || a.agent.username}</td>
                      <td className="p-3 text-right">{formatInr(a.collected)}</td><td className="p-3 text-right">{formatInr(a.held_by_agents)}</td><td className="p-3 text-right">{formatInr(a.in_transit)}</td>
                      <td className="p-3 text-right">{formatInr(a.received_at_branch)}</td><td className={`p-3 text-right ${a.shortfall_total !== "0.00" ? "font-medium text-red-700" : ""}`}>{formatInr(a.shortfall_total)}</td><td className="p-3 text-right">{formatInr(a.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function DashboardPage() {
  return <Suspense fallback={<Spinner />}><Dashboard /></Suspense>;
}
