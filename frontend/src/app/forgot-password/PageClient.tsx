"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

export default function ForgotPasswordPage() {
  useDocumentTitle("Reset your password");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    const body = await post<{ message: string }>("/auth/forgot-password", {
      email: form.get("email"),
    });
    setMessage(body.message);
    setBusy(false);
  }

  return (
    <>
      <PageHeader title="Reset your password" />
      <div className="mx-auto max-w-md px-4 py-8">
        {message ? <Notice kind="good">{message}</Notice> : null}
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="email" className="block font-medium">Email address</label>
            <input id="email" name="email" type="email" required className="field mt-1" />
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
