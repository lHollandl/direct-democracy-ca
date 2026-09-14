"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ApiError, post } from "@/lib/api";
import { useLoader } from "@/components/useLoader";
import { Loading, Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

function Confirm() {
  const token = useSearchParams().get("token");
  const { data } = useLoader<{ ok: boolean; message: string }>(async () => {
    if (!token) {
      return { ok: false, message: "That link is missing its confirmation code." };
    }
    try {
      const body = await post<{ message: string }>("/auth/verify-email", { token });
      return { ok: true, message: body.message };
    } catch (problem) {
      return {
        ok: false,
        message:
          problem instanceof ApiError ? problem.message : "Something went wrong.",
      };
    }
  }, [token]);

  if (!data) return <Loading what="your confirmation" />;
  const state = data.ok ? "done" : "failed";
  const message = data.message;
  return (
    <>
      <Notice kind={state === "done" ? "good" : "bad"}>{message}</Notice>
      <p className="mt-4 text-sm">
        <Link href="/login">Go to sign in</Link>
      </p>
    </>
  );
}

export default function VerifyEmailPage() {
  useDocumentTitle("Confirming your email address");
  return (
    <>
      <PageHeader title="Confirming your email address" />
      <div className="mx-auto max-w-md px-4 py-8">
        <Suspense fallback={<Loading what="your confirmation" />}>
          <Confirm />
        </Suspense>
      </div>
    </>
  );
}
