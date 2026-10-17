export const FREQUENCIES = [
  { value: "DAILY", label: "Daily", unit: "daily" },
  { value: "WEEKLY", label: "Weekly", unit: "weekly" },
  { value: "MONTHLY", label: "Monthly", unit: "monthly" },
  { value: "QUARTERLY", label: "Every 3 months", unit: "every 3 months" },
  { value: "HALF_YEARLY", label: "Every 6 months", unit: "every 6 months" },
] as const;
export type Frequency = (typeof FREQUENCIES)[number]["value"];
export const frequencyUnit = (f: Frequency) => FREQUENCIES.find((x) => x.value === f)?.unit ?? f.toLowerCase();

import type { Branch } from "@/features/auth/types";

export interface AgentRef {
  id: number;
  username: string;
  full_name: string;
}

export interface Customer {
  id: number;
  customer_code: string;
  full_name: string;
  phone: string;
  address: string;
  branch: Branch;
  assigned_agent: AgentRef | null;
  is_active: boolean;
  created_at: string;
}

export type InstallmentStatus = "PAID" | "PARTIAL" | "PENDING" | "OVERDUE";

export interface Installment {
  id: number;
  installment_no: number;
  due_date: string;
  amount_due: string;
  amount_paid: string;
  amount_remaining: string;
  status: InstallmentStatus;
}

export interface Loan {
  id: number;
  loan_number: string;
  customer: { id: number; customer_code: string; full_name: string };
  principal: string;
  total_payable: string;
  installment_count: number;
  frequency: Frequency;
  start_date: string;
  status: "ACTIVE" | "CLOSED";
  paid: string;
  outstanding: string;
  /** Installments due so far minus paid, floored at 0. */
  due_now: string | null;
  created_at: string;
}

export interface Outstanding {
  total_payable: string;
  paid: string;
  outstanding: string;
}
