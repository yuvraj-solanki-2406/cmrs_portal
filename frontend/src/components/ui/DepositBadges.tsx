import { StatusBadge } from "@/components/ui/StatusBadge";
import type { Deposit } from "@/features/treasury/types";

/** Settlement status plus a DELAYED chip while it is still pending past the allowed window. */
export function SettlementBadges({ deposit }: { deposit: Deposit }) {
  return (
    <span className="inline-flex items-center gap-1">
      <StatusBadge status={deposit.settlement.status} />
      {deposit.is_delayed && <StatusBadge status="DELAYED" />}
    </span>
  );
}

export function VarianceChip({ amount }: { amount: string | null }) {
  if (amount === null || amount === "0.00") return <span className="text-slate-400">—</span>;
  return <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-700">{amount.startsWith("-") ? "" : "+"}{amount}</span>;
}
