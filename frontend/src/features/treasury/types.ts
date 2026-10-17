export type SettlementStatus = "PENDING" | "SETTLED" | "FAILED";

export const BANKS: { value: string; label: string }[] = [
  { value: "HDFC", label: "HDFC Bank" },
  { value: "ICICI", label: "ICICI Bank" },
  { value: "SBI", label: "State Bank of India" },
  { value: "AXIS", label: "Axis Bank" },
  { value: "KOTAK", label: "Kotak Mahindra Bank" },
  { value: "PNB", label: "Punjab National Bank" },
  { value: "OTHER", label: "Other" },
];

export interface Settlement {
  status: SettlementStatus;
  settled_amount: string | null;
  settled_on: string | null;
  bank_credit_reference: string;
  variance_amount: string | null;
  variance_note: string;
  failure_reason: string;
  confirmed_by: string | null;
  confirmed_at: string | null;
}

export interface Deposit {
  id: number;
  deposit_no: string;
  branch: string;
  bank_name: string;
  amount: string;
  deposit_date: string;
  reference_number: string;
  reconciled_amount: string;
  variance_amount: string;
  variance_note: string;
  created_by: string;
  created_at: string;
  submission_count: number;
  settlement: Settlement;
  is_delayed: boolean;
  gap_amount: string | null;
  submissions?: { id: number; reference_no: string; agent: string; received_amount: string; discrepancy_amount: string }[];
}

export interface EligibleSubmission {
  id: number;
  reference_no: string;
  agent: string;
  submitted_at: string;
  expected_amount: string;
  received_amount: string;
  discrepancy_amount: string;
}
