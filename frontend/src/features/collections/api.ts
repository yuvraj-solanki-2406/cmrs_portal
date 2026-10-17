import { api, type Paginated } from "@/lib/apiClient";
import type { Collection, CollectionSummary } from "./types";

export interface CollectionFilters {
  page?: number;
  agent?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export const listCollections = (f: CollectionFilters) => api<Paginated<Collection>>("/collections/", { query: { ...f } });
export const collectionSummary = (f: CollectionFilters) => api<CollectionSummary>("/collections/summary/", { query: { ...f, page: undefined } });
export const loanRepayments = (loanId: number | string) => api<Collection[]>(`/loans/${loanId}/repayments/`);

export const recordRepayment = (
  body: { loan: number; amount: string; note: string; confirm_duplicate?: boolean },
  idempotencyKey: string,
) => api<Collection>("/collections/", { method: "POST", body, idempotencyKey });

export const voidCollection = (id: number, reason: string) =>
  api<Collection>(`/collections/${id}/void/`, { method: "POST", body: { reason } });
