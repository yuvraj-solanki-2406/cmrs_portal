import type { InputHTMLAttributes, ReactNode } from "react";
import { cleanAmount, groupIndian } from "@/lib/money";

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm shadow-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/40";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

export function PrimaryButton({ children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button {...rest} className={`bg-gradient-to-b from-accent to-brand px-4 py-2 text-sm font-semibold text-white hover:from-brand hover:to-brand-dark disabled:opacity-50 ${rest.className ?? ""}`}>
      {children}
    </button>
  );
}

/** Amount input that shows Indian grouping (5,00,000) while the value it reports stays a raw string ("500000"). */
export function MoneyInput({ value, onChange, ...rest }: Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  value: string; onChange: (raw: string) => void;
}) {
  return (
    <Input
      {...rest}
      inputMode="decimal"
      autoComplete="off"
      value={groupIndian(value ?? "")}
      onChange={(e) => {
        const el = e.target;
        const digitsBeforeCaret = el.value.slice(0, el.selectionStart ?? el.value.length).replace(/[^\d.]/g, "").length;
        const raw = cleanAmount(el.value);
        onChange(raw);
        // Keep the caret next to the same digit after the commas are re-inserted.
        requestAnimationFrame(() => {
          const shown = groupIndian(raw);
          let seen = 0, pos = 0;
          while (pos < shown.length && seen < digitsBeforeCaret) { if (/[\d.]/.test(shown[pos])) seen++; pos++; }
          el.setSelectionRange(pos, pos);
        });
      }}
    />
  );
}
