import { api, type Paginated } from "@/lib/apiClient";
import type { AuditEvent, BranchSummaryRow, DiscrepancyRow, Lifecycle, MismatchRow, ReportFilters, StageRecords, Summary } from "./types";

export const getSummary = (f: ReportFilters) => api<Summary>("/dashboard/summary/", { query: { ...f, stage: undefined } });
export const getStageRecords = (f: ReportFilters) => api<StageRecords>("/dashboard/records/", { query: { ...f } });
export const getBranchSummary = (f: ReportFilters) =>
  api<{ branches: BranchSummaryRow[] }>("/dashboard/branch-summary/", { query: { ...f, stage: undefined, agent: undefined } });
export const getDiscrepancies = (f: ReportFilters & { page?: number }) =>
  api<Paginated<DiscrepancyRow>>("/reports/discrepancies/", { query: { ...f, stage: undefined } });
export const getMismatches = (f: ReportFilters) => api<{ rows: MismatchRow[] }>("/reports/mismatches/", { query: { ...f, stage: undefined } });
export const getLifecycle = (type: string, id: string) => api<Lifecycle>(`/reports/lifecycle/${type}/${id}/`);
export const listAuditEvents = (q: { page?: number; entity_type?: string; entity_id?: string; action?: string }) =>
  api<Paginated<AuditEvent>>("/audit-events/", { query: { ...q } });
