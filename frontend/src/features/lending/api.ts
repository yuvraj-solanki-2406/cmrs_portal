import { api, type Paginated } from "@/lib/apiClient";
import type { User } from "@/features/auth/types";
import type { Customer, Frequency, Installment, Loan, Outstanding } from "./types";

export interface CustomerFilters {
  page?: number;
  search?: string;
  assigned_agent?: string;
  is_active?: string;
}

export const listCustomers = (f: CustomerFilters) => api<Paginated<Customer>>("/customers/", { query: { ...f } });
export const getCustomer = (id: number | string) => api<Customer>(`/customers/${id}/`);
export const createCustomer = (body: {
  full_name: string; phone: string; address: string; branch?: number | null; assigned_agent?: number | null;
}) => api<Customer>("/customers/", { method: "POST", body });
export const assignAgent = (id: number, agent: number | null) =>
  api<Customer>(`/customers/${id}/assign-agent/`, { method: "POST", body: { agent } });

export const listAgents = (branch?: number) => api<User[]>("/agents/", { query: { branch } });

export const listLoans = (query: { customer?: number | string; page?: number }) =>
  api<Paginated<Loan>>("/loans/", { query });
export const getLoan = (id: number | string) => api<Loan>(`/loans/${id}/`);
export const getInstallments = (id: number | string) => api<Installment[]>(`/loans/${id}/installments/`);
export const getOutstanding = (id: number | string) => api<Outstanding>(`/loans/${id}/outstanding/`);
export const createLoan = (body: {
  customer: number; principal: string; total_payable: string; installment_count: number;
  frequency: Frequency; start_date: string;
}) => api<Loan & { installments: Installment[] }>("/loans/", { method: "POST", body });
