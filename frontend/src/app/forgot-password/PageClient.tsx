"use client";

import { useRef, useState } from "react";
import { post } from "@/lib/api";
import { Notice, PageHeader } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

export default function ForgotPasswordPage() {
  useDocumentTitle("Reset your password");
  const [message, setMessage] = useState<string | null>(null);
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const body = await post<{ message: string }>("/auth/forgot-password", {
        email: form.get("email"),
      });
      setMessage(body.message);
    } catch (problem) {
      fail(problem, formRef.current);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Reset your password" />
      <div className="mx-auto max-w-md px-4 py-8">
        {message ? <Notice kind="good">{message}</Notice> : null}
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
              className="field mt-1"
              {...fieldProps("email")}
            />
            <FieldError name="email" fieldErrors={fieldErrors} />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={busy}>
            {busy ? "Sending…" : "Send me a reset link"}
          </button>
        </form>
        <p className="mt-4 text-sm text-[var(--muted)]">
          We answer the same way whether or not that address has an account, so
          this page cannot be used to find out who is a member.
        </p>
      </div>
    </>
  );
}
