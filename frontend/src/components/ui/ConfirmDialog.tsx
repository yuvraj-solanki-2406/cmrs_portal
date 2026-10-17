"use client";

import { Modal } from "./Modal";

export function ConfirmDialog({
  open, title, message, confirmLabel = "Confirm", onConfirm, onCancel,
}: {
  open: boolean; title: string; message: string; confirmLabel?: string; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel}>
      <p className="text-sm text-slate-600">{message}</p>
      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium hover:bg-secondary">Cancel</button>
        <button onClick={onConfirm} className="rounded bg-gradient-to-b from-accent to-brand font-medium px-3 py-1.5 text-sm text-white">{confirmLabel}</button>
      </div>
    </Modal>
  );
}
