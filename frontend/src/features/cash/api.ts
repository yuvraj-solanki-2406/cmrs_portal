import { api, type Paginated } from "@/lib/apiClient";
import type { PendingCollections, Submission } from "./types";

export interface SubmissionFilters {
  page?: number;
  status?: string;
  agent?: string;
  date_from?: string;
  date_to?: string;
}

export const pendingCollections = () => api<PendingCollections>("/submissions/pending-collections/");
export const listSubmissions = (f: SubmissionFilters) => api<Paginated<Submission>>("/submissions/", { query: { ...f } });
export const getSubmission = (id: number | string) => api<Submission>(`/submissions/${id}/`);
export const submitCash = (collectionIds: number[], note: string, idempotencyKey: string) =>
  api<Submission>("/submissions/", { method: "POST", body: { collection_ids: collectionIds, note }, idempotencyKey });
export const approveSubmission = (id: number, received_amount: string, discrepancy_reason: string) =>
  api<Submission>(`/submissions/${id}/approve/`, { method: "POST", body: { received_amount, discrepancy_reason } });
export const rejectSubmission = (id: number, reason: string) =>
  api<Submission>(`/submissions/${id}/reject/`, { method: "POST", body: { reason } });
