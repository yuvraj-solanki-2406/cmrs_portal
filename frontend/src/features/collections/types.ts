export interface Collection {
  id: number;
  receipt_number: string;
  loan: { id: number; loan_number: string };
  customer: { id: number; customer_code: string; full_name: string };
  agent: { id: number; username: string; full_name: string };
  branch: string;
  amount: string;
  collected_at: string;
  collection_date: string;
  status: "VALID" | "VOIDED";
  note: string;
  voided_at: string | null;
  void_reason: string;
}

export interface CollectionSummary {
  count: number;
  total_amount: string;
}
