export interface Metrics {
  expected: string; collected: string; held_by_agents: string; in_transit: string; received_at_branch: string;
  deposited: string; settled: string; outstanding: string;
  discrepancy_total: string; discrepancy_count: number; shortfall_total: string; surplus_total: string;
  deposit_variance_total: string; deposit_variance_count: number;
  settlement_variance_total: string; settlement_variance_count: number;
  delayed_settlements: number | null; pending_settlement_amount: string | null;
}
export interface FunnelStage { stage: string; label: string; amount: string }
export interface Summary { metrics: Metrics; funnel: FunnelStage[]; attribution: "deposit" | "submission" }

export interface StageRow {
  kind: "collection" | "submission" | "deposit"; id: number; reference: string; date: string; branch: string;
  agent: string; party: string; amount: string; status: string;
}
export interface StageRecords { stage: string; total: number; truncated: boolean; rows: StageRow[] }

export interface AgentSummary {
  agent: { id: number; username: string; full_name: string };
  collected: string; held_by_agents: string; in_transit: string; received_at_branch: string; shortfall_total: string; outstanding: string;
}
export interface BranchSummaryRow {
  branch: { id: number; code: string; name: string };
  expected: string; collected: string; held_by_agents: string; in_transit: string; received_at_branch: string;
  deposited: string; settled: string; outstanding: string; discrepancy_total: string; delayed_settlements: number | null;
  agents: AgentSummary[];
}

export interface DiscrepancyRow {
  id: number; reference_no: string; agent: string; branch: string; reviewed_at: string; reviewed_by: string;
  expected_amount: string; received_amount: string; discrepancy_amount: string; discrepancy_reason: string;
}
export interface MismatchRow {
  type: "DEPOSIT_VS_RECONCILED" | "SETTLED_VS_DEPOSITED" | "SETTLEMENT_FAILED" | "SETTLEMENT_DELAYED";
  deposit_id: number; deposit_no: string; branch: string; date: string; expected: string; actual: string | null;
  difference: string | null; reason: string; settlement_status: string;
}

export interface TimelineEvent {
  at: string; action: string; actor: string | null; actor_role: string; entity_type: string; entity_id: string;
  reason: string; details: Record<string, unknown> | null;
}
export interface Lifecycle {
  root: { type: string; id: number };
  collections: { id: number; receipt_number: string; amount: string; status: string; collected_at: string; agent: string; customer: string; loan_number: string; void_reason: string }[];
  submissions: { id: number; reference_no: string; status: string; agent: string; submitted_at: string; expected_amount: string; received_amount: string | null; discrepancy_amount: string | null; discrepancy_reason: string; reviewed_by: string | null; reviewed_at: string | null; rejection_reason: string; deposit_id: number | null }[];
  deposits: { id: number; deposit_no: string; bank_name: string; deposit_date: string; settlement_status: string; is_delayed: boolean; settled_on: string | null; reference_number?: string; amount?: string; reconciled_amount?: string; variance_amount?: string; variance_note?: string; settled_amount?: string | null; settlement_variance?: string | null; settlement_variance_note?: string; failure_reason?: string; confirmed_by?: string | null }[];
  timeline: TimelineEvent[];
}

export interface AuditEvent {
  id: number; occurred_at: string; actor: string | null; actor_role: string; action: string; entity_type: string;
  entity_id: string; before: unknown; after: unknown; reason: string; request_id: string;
}

export interface ReportFilters { date_from?: string; date_to?: string; branch?: string; agent?: string; stage?: string }
