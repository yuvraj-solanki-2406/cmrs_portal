"use client";

import { useState } from "react";

import { Modal } from "./Modal";

/** Dialog that requires a typed reason before a destructive/irreversible action (void, reject, fail). */
export function ReasonDialog({
  open, title, description, actionLabel, onSubmit, onCancel, error, busy,
}: {
  open: boolean; title: string; description: string; actionLabel: string; onSubmit: (reason: string) => void;
  onCancel: () => void; error?: string | null; busy?: boolean;
}) {
  const [reason, setReason] = useState("");
  const close = () => { setReason(""); onCancel(); };
  return (
    <Modal open={open} title={title} onClose={close}>
      <p className="text-sm text-slate-600">{description}</p>
      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Reason (required)</span>
        <input value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)}
          className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500" />
      </label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex justify-end gap-2 pt-1">
        <button onClick={close} className="border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium hover:bg-secondary">Cancel</button>
        <button disabled={!reason.trim() || busy} onClick={() => onSubmit(reason.trim())}
          className="rounded bg-red-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">{actionLabel}</button>
      </div>
    </Modal>
  );
}
