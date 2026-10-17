import { ApiError } from "@/lib/apiClient";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 p-6 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
      {label}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{message}</div>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError ? error.userMessage : "Something went wrong.";
  const requestId = error instanceof ApiError ? error.body.request_id : undefined;
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <p className="font-medium">{message}</p>
      {requestId && <p className="mt-1 text-xs text-red-600">Reference: {requestId}</p>}
      {onRetry && (
        <button onClick={onRetry} className="mt-2 rounded bg-red-600 px-3 py-1 text-white hover:bg-red-700">
          Retry
        </button>
      )}
    </div>
  );
}
