"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { Spinner } from "@/components/ui/states";
import { EXTRA_ROUTES, ROLE_LABELS, navFor } from "@/lib/roles";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <Spinner label="Checking session…" />;

  const nav = navFor(user.role);
  // UX-only guard; the API rejects unauthorized calls regardless.
  const allowed =
    nav.some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)) ||
    EXTRA_ROUTES.some((r) => pathname.startsWith(r.prefix) && r.roles.includes(user.role));

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <aside className="w-60 shrink-0 bg-gradient-to-b from-ink via-ink to-[#10236f] p-4 text-primary shadow-xl">
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-brand text-sm font-bold text-white shadow-md">₹</span>
          <div className="leading-tight"><p className="text-lg font-semibold tracking-wide">CMRS</p><p className="text-[11px] text-tertiary">Cash &amp; Reconciliation</p></div>
        </div>
        <nav aria-label="Main" className="mt-6 space-y-1">
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}
                className={`block rounded-lg px-3 py-2.5 text-sm transition ${active ? "bg-gradient-to-r from-accent to-brand font-medium text-white shadow-md" : "text-tertiary hover:bg-white/10 hover:text-white"}`}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between bg-white/90 px-6 py-3 text-ink shadow-sm backdrop-blur">
          <div className="text-sm">
            <span className="font-medium">{user.full_name || user.username}</span>
            <span className="ml-2 text-slate-600">
              {ROLE_LABELS[user.role]}{user.branch ? ` · ${user.branch.name}` : ""}
            </span>
          </div>
          <button onClick={() => void logout()} className="border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-ink hover:border-accent hover:bg-secondary">
            Sign out
          </button>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 p-6 outline-none">
          {allowed ? children : <p className="text-sm text-slate-600">You do not have access to this page.</p>}
        </main>
      </div>
    </div>
  );
}
