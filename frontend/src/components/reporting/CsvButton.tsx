"use client";

import { useState } from "react";

import { downloadCsv } from "@/lib/apiClient";

export function CsvButton({ path, query, filename }: { path: string; query: Record<string, string | undefined>; filename: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="inline-flex items-center gap-2">
      <button disabled={busy} className="border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-ink hover:border-accent hover:bg-secondary disabled:opacity-50"
        onClick={async () => { setBusy(true); setError(null); try { await downloadCsv(path, query, filename); } catch { setError("Export failed"); } finally { setBusy(false); } }}>
        {busy ? "Exporting…" : "Export CSV"}
      </button>
      {error && <span role="alert" className="text-xs text-red-700">{error}</span>}
    </span>
  );
}
