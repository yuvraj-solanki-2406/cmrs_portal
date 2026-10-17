"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAuth } from "@/features/auth/AuthProvider";
import { Field, Input, PrimaryButton } from "@/components/ui/form";
import { ApiError } from "@/lib/apiClient";

const schema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { user, login } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await login(values.username, values.password);
      router.replace("/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? (err.status === 401 ? "Invalid username or password." : err.userMessage) : "Unable to sign in.");
    }
  });

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Left: brand panel with an illustration of the cash pipeline */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-ink via-[#0d2090] to-brand p-12 text-white lg:flex">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-accent/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-tertiary/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/15 text-xl font-bold shadow-lg ring-1 ring-white/30 backdrop-blur">₹</span>
          <span className="text-xl font-semibold tracking-wide">CMRS</span>
        </div>

        <div className="relative space-y-8">
          <div>
            <h2 className="text-4xl font-semibold leading-tight">Every rupee collected,<br />tracked to the bank.</h2>
            <p className="mt-4 max-w-md text-base text-tertiary">
              Record repayments in the field, reconcile at the branch, deposit and settle with finance. One trail, nothing lost.
            </p>
          </div>
          <PipelineIllustration />
        </div>

        <p className="relative text-sm text-tertiary/80">Cash Management &amp; Reconciliation System</p>
      </section>

      {/* Right: sign-in form */}
      <section className="flex items-center justify-center bg-white p-6 sm:p-12">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
          <div className="flex items-center gap-2.5 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-brand font-bold text-white shadow-md">₹</span>
            <span className="text-lg font-semibold text-ink">CMRS</span>
          </div>
          <div>
            <h1 className="text-3xl font-semibold text-ink">Welcome back</h1>
            <p className="mt-1.5 text-sm text-slate-500">Sign in to continue to your workspace.</p>
          </div>
          <Field label="Username" error={errors.username?.message}>
            <Input autoComplete="username" placeholder="Enter your username" {...register("username")} />
          </Field>
          <Field label="Password" error={errors.password?.message}>
            <Input type="password" autoComplete="current-password" placeholder="Enter your password" {...register("password")} />
          </Field>
          {serverError && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{serverError}</p>}
          <PrimaryButton type="submit" disabled={isSubmitting} className="w-full !py-3 text-base">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </PrimaryButton>
        </form>
      </section>
    </main>
  );
}

const STEPS = ["Collect", "Submit", "Reconcile", "Deposit", "Settle"];

function PipelineIllustration() {
  return (
    <div aria-hidden="true" className="rounded-2xl bg-white/10 p-6 shadow-2xl ring-1 ring-white/20 backdrop-blur">
      <svg viewBox="0 0 520 150" className="w-full">
        <defs>
          <linearGradient id="line" x1="0" x2="1"><stop offset="0" stopColor="#ABD2FA" /><stop offset="1" stopColor="#7692FF" /></linearGradient>
        </defs>
        <path d="M40 60 H480" stroke="url(#line)" strokeWidth="3" strokeLinecap="round" strokeDasharray="2 8" />
        {STEPS.map((label, i) => {
          const x = 40 + i * 110;
          return (
            <g key={label}>
              <circle cx={x} cy="60" r="26" fill="#fff" fillOpacity={0.18 + i * 0.07} stroke="#ABD2FA" strokeWidth="1.5" />
              <text x={x} y="67" textAnchor="middle" fontSize="20" fontWeight="700" fill="#fff">{i + 1}</text>
              <text x={x} y="115" textAnchor="middle" fontSize="13" fill="#ABD2FA">{label}</text>
            </g>
          );
        })}
      </svg>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs text-tertiary">
        <div className="rounded-lg bg-white/10 p-3"><p className="text-lg font-semibold text-white">4</p>user roles</div>
        <div className="rounded-lg bg-white/10 p-3"><p className="text-lg font-semibold text-white">5</p>step lifecycle</div>
        <div className="rounded-lg bg-white/10 p-3"><p className="text-lg font-semibold text-white">Full</p>audit trail</div>
      </div>
    </div>
  );
}
