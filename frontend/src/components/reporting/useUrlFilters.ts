"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** Filters live in the URL so a view can be shared, bookmarked and survives refresh. */
export function useUrlFilters<T extends Record<string, string>>(defaults: T) {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const values = Object.fromEntries(Object.keys(defaults).map((k) => [k, params.has(k) ? (params.get(k) ?? "") : defaults[k]])) as T;
  const set = useCallback((patch: Partial<T>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) next.set(k, v ?? "");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [params, pathname, router]);
  return [values, set] as const;
}
