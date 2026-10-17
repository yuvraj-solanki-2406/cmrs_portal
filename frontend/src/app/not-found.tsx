import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="max-w-md space-y-3 rounded-lg bg-white p-6 text-center shadow">
        <h1 className="text-xl font-semibold">Page not found</h1>
        <p className="text-sm text-slate-600">The page you are looking for does not exist or you do not have access to it.</p>
        <Link href="/dashboard" className="inline-block rounded bg-gradient-to-b from-accent to-brand font-medium px-4 py-2 text-sm text-white">Go to dashboard</Link>
      </div>
    </main>
  );
}
