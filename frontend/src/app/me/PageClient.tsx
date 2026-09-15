"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { apiBase, del, patch, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Loading, Notice, PageHeader, Section } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

const MODES = [
  ["display_name", "My display name", "Most people show this."],
  ["real_name", "My real name", "Everything you write is signed with your real name."],
  ["anonymous", "Anonymous Community Member", "Your name is never shown beside anything you write. Your vote still counts the same."],
];

export default function MePage() {
  useDocumentTitle("Your account");
  const router = useRouter();
  const { me, loading, reload, signOut } = useSession();
  const [message, setMessage] = useState<string | null>(null);
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [exportId, setExportId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const deleteFormRef = useRef<HTMLFormElement>(null);

  if (loading) return <Loading what="your account" />;
  if (!me) {
    return (
      <>
        <PageHeader title="Your account" />
        <div className="mx-auto max-w-md px-4 py-8">
          <Notice>You need to <Link href="/login">sign in</Link> to see this page.</Notice>
        </div>
      </>
    );
  }

  async function changeMode(mode: string) {
    clear();
    try {
      const body = await patch<{ shown_as: string }>("/me/display", {
        public_name_mode: mode,
      });
      setMessage(`Everything you write now shows as “${body.shown_as}”.`);
      await reload();
    } catch (problem) {
      fail(problem);
    }
  }

  async function requestExport() {
    clear();
    const body = await post<{ id: number; message: string }>("/me/export");
    setExportId(body.id);
    setMessage(body.message);
  }

  async function deleteAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    const form = new FormData(event.currentTarget);
    try {
      await del("/me", {
        password: form.get("password"),
        understand_this_cannot_be_undone: true,
      });
      await signOut();
      router.push("/");
    } catch (problem) {
      fail(problem, deleteFormRef.current);
    }
  }

  return (
    <>
      <PageHeader title="Your account" lead={me.display_name} />
      <div className="mx-auto max-w-2xl px-4 py-8">
        {message ? <Notice kind="good">{message}</Notice> : null}
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}

        <Section title="Your communities" description="You can read anywhere. You post and vote in these three.">
          <ul className="flex flex-wrap gap-2">
            {me.home_communities.map((community) => (
              <li key={`${community.level}:${community.entity_id}`} className="badge">
                {community.label}
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="Your verification level"
          description={me.verification_level}
        >
          <p className="text-sm text-[var(--muted)]">{me.verification_explanation}</p>
        </Section>

        <Section title="How your name appears" description="This is a setting, not an account type. You can change it whenever you like.">
          <fieldset className="space-y-2">
            <legend className="sr-only">How your name appears</legend>
            {MODES.map(([value, label, explanation]) => (
              <label key={value} className="flex items-start gap-2 rounded-lg border border-[var(--line)] p-3">
                <input
                  type="radio"
                  name="public_name_mode"
                  value={value}
                  className="mt-1"
                  defaultChecked={me.public_name_mode === value}
                  onChange={() => void changeMode(value)}
                />
                <span>
                  <span className="font-medium">{label}</span>
                  <span className="block text-sm text-[var(--muted)]">{explanation}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </Section>

        <Section
          title="Take your data with you"
          description="Everything the platform holds about you, as a JSON file. Your ballot votes are in it, and they are shown to nobody else."
        >
          <button type="button" className="btn" onClick={() => void requestExport()}>
            Prepare my data
          </button>
          {exportId ? (
            <p className="mt-2 text-sm">
              <a href={`${apiBase()}/me/export/${exportId}`}>Download it</a> — give
              it a moment if it is not ready yet.
            </p>
          ) : null}
        </Section>

        <Section
          title="Delete your account"
          description="Your name, email, password, date of birth, gender and political party are erased permanently."
        >
          <p className="text-sm text-[var(--muted)]">
            What you wrote stays in the civic record, attributed to “Former
            Community Member”, because other people built on it. Your home city
            and county are kept so that record stays in the right community;
            neither identifies you on its own. Cryptographic fingerprints are
            never deleted — they are public proofs, not personal data.
          </p>
          {confirming ? (
            <form
              ref={deleteFormRef}
              onSubmit={deleteAccount}
              className="mt-3 space-y-3"
              noValidate
            >
              <div>
                <label htmlFor="password" className="block font-medium">
                  Confirm with your password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="field mt-1"
                  {...fieldProps("password")}
                />
                <FieldError name="password" fieldErrors={fieldErrors} />
              </div>
              <div className="flex gap-2">
                <button type="submit" className="btn" style={{ borderColor: "var(--bad)", color: "var(--bad)" }}>
                  Delete my account permanently
                </button>
                <button type="button" className="btn" onClick={() => setConfirming(false)}>
                  Keep my account
                </button>
              </div>
            </form>
          ) : (
            <button type="button" className="btn mt-3" onClick={() => setConfirming(true)}>
              I want to delete my account
            </button>
          )}
        </Section>
      </div>
    </>
  );
}
