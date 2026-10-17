"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { inputClass } from "@/components/ui/form";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/states";
import { listAuditEvents } from "@/features/reporting/api";

const ENTITIES = ["", "Collection", "CashSubmission", "BankDeposit", "Settlement", "Loan", "Customer", "User", "Branch"];

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const q = { page, entity_type: entityType, entity_id: entityId };
  const list = useQuery({ queryKey: ["audit", q], queryFn: () => listAuditEvents(q), placeholderData: keepPreviousData });
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <p className="text-sm text-slate-600">Append-only record of every sensitive change. Managers see events by users of their branch.</p>
      <div className="flex flex-wrap gap-3">
        <select className={`${inputClass} max-w-xs`} value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(1); }}>{ENTITIES.map((e) => <option key={e} value={e}>{e || "All entities"}</option>)}</select>
        <input className={`${inputClass} max-w-[10rem]`} placeholder="Entity id" value={entityId} onChange={(e) => { setEntityId(e.target.value.replace(/\D/g, "")); setPage(1); }} />
      </div>
      {list.isLoading && <Spinner />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.results.length === 0 && <EmptyState message="No events match." />}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600"><tr><th scope="col" className="p-3">When</th><th scope="col" className="p-3">Who</th><th scope="col" className="p-3">Action</th><th scope="col" className="p-3">Entity</th><th scope="col" className="p-3">Reason / details</th></tr></thead>
            <tbody>
              {list.data.results.map((e) => (
                <tr key={e.id} className="border-b align-top last:border-0">
                  <td className="p-3 whitespace-nowrap">{new Date(e.occurred_at).toLocaleString("en-IN")}</td>
                  <td className="p-3">{e.actor ?? "system"} <span className="text-xs text-slate-500">{e.actor_role}</span></td>
                  <td className="p-3 font-medium">{e.action.replaceAll("_", " ")}</td>
                  <td className="p-3">{e.entity_type} #{e.entity_id}</td>
                  <td className="p-3 text-xs text-slate-600">{e.reason && <p>{e.reason}</p>}{e.after !== null && <code className="break-all">{JSON.stringify(e.after)}</code>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm text-slate-600"><span>{list.data.count} events</span>
            <div className="space-x-2"><button disabled={!list.data.previous} onClick={() => setPage((p) => p - 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Prev</button><button disabled={!list.data.next} onClick={() => setPage((p) => p + 1)} className="border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-secondary disabled:opacity-40">Next</button></div></div>
        </div>
      )}
    </section>
  );
}
