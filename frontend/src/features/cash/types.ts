import type { Collection } from "@/features/collections/types";

export type SubmissionStatus = "SUBMITTED" | "APPROVED" | "REJECTED";

export interface SubmissionItem {
  id: number;
  collection: number;
  receipt_number: string;
  customer: string;
  loan_number: string;
  amount: string;
  is_active: boolean;
}

export interface Submission {
  id: number;
  reference_no: string;
  agent: { id: number; username: string; full_name: string };
  branch: string;
  submitted_at: string;
  status: SubmissionStatus;
  expected_amount: string;
  received_amount: string | null;
  discrepancy_amount: string | null;
  discrepancy_reason: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  rejection_reason: string;
  note: string;
  item_count: number;
  items?: SubmissionItem[];
}

export interface PendingCollections {
  collections: Collection[];
  count: number;
  total: string;
  in_transit: string;
  open_shortfall: string;
}
