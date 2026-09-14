"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, signIn } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

export default function LoginPage() {
  useDocumentTitle("Sign in");
  const router = useRouter();
  const { reload } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await signIn(String(form.get("email")), String(form.get("password")));
      await reload();
      router.push("/feed");
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Sign in" />
      <div className="mx-auto max-w-md px-4 py-8">
        {error ? <Notice kind="bad">{error}</Notice> : null}
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="email" className="block font-medium">Email address</label>
            <input id="email" name="email" type="email" required autoComplete="email" className="field mt-1" />
          </div>
          <div>
            <label htmlFor="password" className="block font-medium">Password</label>
            <input id="password" name="password" type="password" required autoComplete="current-password" className="field mt-1" />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-sm">
          <Link href="/forgot-password">Forgotten your password?</Link>
        </p>
        <p className="mt-1 text-sm">
          No account yet? <Link href="/signup">Join your community</Link>.
        </p>
      </div>
    </>
  );
}
