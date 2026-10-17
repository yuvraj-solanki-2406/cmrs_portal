const TONES: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-800",
  INACTIVE: "bg-secondary text-slate-600",
  PENDING: "bg-amber-100 text-amber-800",
  SUBMITTED: "bg-blue-100 text-blue-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
  SETTLED: "bg-emerald-100 text-emerald-800",
  FAILED: "bg-red-100 text-red-800",
  DELAYED: "bg-orange-100 text-orange-800",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TONES[status] ?? "bg-secondary text-ink"}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
