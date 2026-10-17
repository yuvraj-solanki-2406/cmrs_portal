import { api, type Paginated } from "@/lib/apiClient";
import type { Deposit, EligibleSubmission } from "./types";

export interface DepositFilters {
  page?: number;
  status?: string;
  delayed?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export const listDeposits = (f: DepositFilters) => api<Paginated<Deposit>>("/deposits/", { query: { ...f } });
export const getDeposit = (id: number | string) => api<Deposit>(`/deposits/${id}/`);
export const eligibleSubmissions = () => api<EligibleSubmission[]>("/deposits/eligible-submissions/");
export const recordDeposit = (body: {
  submission_ids: number[]; bank_name: string; amount: string; deposit_date: string;
  reference_number: string; variance_note: string;
}) => api<Deposit>("/deposits/", { method: "POST", body });
export const confirmSettlement = (id: number, body: {
  settled_amount: string; settled_on: string; variance_note: string; bank_credit_reference: string;
}) => api<Deposit>(`/deposits/${id}/settlement/confirm/`, { method: "POST", body });
export const failSettlement = (id: number, reason: string) =>
  api<Deposit>(`/deposits/${id}/settlement/fail/`, { method: "POST", body: { reason } });
