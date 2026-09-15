"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { signIn } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Notice, PageHeader } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

export default function LoginPage() {
  useDocumentTitle("Sign in");
  const router = useRouter();
  const { reload } = useSession();
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await signIn(String(form.get("email")), String(form.get("password")));
      await reload();
      router.push("/feed");
    } catch (problem) {
      fail(problem, formRef.current);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Sign in" />
      <div className="mx-auto max-w-md px-4 py-8">
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}
        <form ref={formRef} onSubmit={onSubmit} className="mt-4 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block font-medium">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              className="field mt-1"
              {...fieldProps("email")}
            />
            <FieldError name="email" fieldErrors={fieldErrors} />
          </div>
          <div>
            <label htmlFor="password" className="block font-medium">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className="field mt-1"
              {...fieldProps("password")}
            />
            <FieldError name="password" fieldErrors={fieldErrors} />
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
