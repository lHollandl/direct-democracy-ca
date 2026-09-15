"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { post } from "@/lib/api";
import { Loading, Notice, PageHeader } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
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
      const body = await post<{ message: string }>("/auth/reset-password", {
        token,
        new_password: form.get("new_password"),
      });
      setMessage(body.message);
    } catch (problem) {
      fail(problem, formRef.current);
    } finally {
      setBusy(false);
    }
  }

  if (message) {
    return (
      <>
        <Notice kind="good">{message}</Notice>
        <p className="mt-4 text-sm"><Link href="/login">Sign in</Link></p>
      </>
    );
  }

  return (
    <>
      {error ? (
        <Notice kind="bad" alertRef={alertRef}>
          {error}
        </Notice>
      ) : null}
      <form ref={formRef} onSubmit={onSubmit} className="mt-4 space-y-4" noValidate>
        <div>
          <label htmlFor="new_password" className="block font-medium">New password</label>
          <input
            id="new_password"
            name="new_password"
            type="password"
            required
            autoComplete="new-password"
            className="field mt-1"
            {...fieldProps("new_password", "new_password-hint")}
          />
          <FieldError name="new_password" fieldErrors={fieldErrors} />
          <p id="new_password-hint" className="mt-1 text-sm text-[var(--muted)]">
            At least 8 characters, with a capital letter and a number, and at
            most 72 bytes long (most letters are 1 byte each; some accented
            or non-English letters count as more).
          </p>
        </div>
        <button type="submit" className="btn btn-primary w-full" disabled={busy || !token}>
          {busy ? "Changing it…" : "Change my password"}
        </button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  useDocumentTitle("Choose a new password");
  return (
    <>
      <PageHeader title="Choose a new password" />
      <div className="mx-auto max-w-md px-4 py-8">
        <Suspense fallback={<Loading what="the form" />}>
          <ResetForm />
        </Suspense>
      </div>
    </>
  );
}
