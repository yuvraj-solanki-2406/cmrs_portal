// Money arrives from the API as decimal strings. We only format for display; no arithmetic on floats.
const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

export function formatInr(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return inr.format(value as unknown as number);
}

export const MONEY_PATTERN = /^\d{1,12}(\.\d{1,2})?$/;

/** Display-only helpers using integer paise (BigInt) so no floating-point arithmetic is involved. */
export function toPaise(value: string): bigint | null {
  if (!MONEY_PATTERN.test(value)) return null;
  const [rupees, paise = ""] = value.split(".");
  return BigInt(rupees) * 100n + BigInt(paise.padEnd(2, "0"));
}

export function fromPaise(paise: bigint): string {
  const negative = paise < 0n;
  const abs = negative ? -paise : paise;
  return `${negative ? "-" : ""}${abs / 100n}.${(abs % 100n).toString().padStart(2, "0")}`;
}

/** a - b as a decimal string, or null if either input is not a valid amount. */
export function subtractMoney(a: string, b: string): string | null {
  const pa = toPaise(a), pb = toPaise(b);
  return pa === null || pb === null ? null : fromPaise(pa - pb);
}

/** Sum of decimal strings (all must be valid). */
export function sumMoney(values: string[]): string {
  return fromPaise(values.reduce((acc, v) => acc + (toPaise(v) ?? 0n), 0n));
}

/** "500000.5" -> "5,00,000.5" (Indian digit grouping) for live display in amount inputs. Input is a raw amount string. */
export function groupIndian(raw: string): string {
  const [int, dec] = raw.split(".");
  const head = int.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  const grouped = int.length > 3 ? `${head},${int.slice(-3)}` : int;
  return dec === undefined ? grouped : `${grouped}.${dec}`;
}

/** Strip everything but digits and a single dot; max 12 integer digits and 2 decimals. */
export function cleanAmount(text: string): string {
  const t = text.replace(/[^\d.]/g, "");
  const i = t.indexOf(".");
  if (i === -1) return t.slice(0, 12);
  return `${t.slice(0, i).slice(0, 12)}.${t.slice(i + 1).replace(/\./g, "").slice(0, 2)}`;
}
