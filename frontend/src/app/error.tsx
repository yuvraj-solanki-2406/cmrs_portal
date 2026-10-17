"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div role="alert" className="max-w-md space-y-3 rounded-lg bg-white p-6 text-center shadow">
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="text-sm text-slate-600">The page hit an unexpected problem. Your data is safe: nothing was changed by this error.</p>
        {error.digest && <p className="text-xs text-slate-500">Reference: {error.digest}</p>}
        <button onClick={reset} className="rounded bg-gradient-to-b from-accent to-brand font-medium px-4 py-2 text-sm text-white">Try again</button>
      </div>
    </main>
  );
}
