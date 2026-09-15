"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, get, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Umbrella = { id: number; name: string; statement: string; main_category: string | null };

export default function NewPostPage() {
  useDocumentTitle("Write down a problem");
  const router = useRouter();
  const { me, loading } = useSession();
  const [problem, setProblem] = useState("");
  const [solutions, setSolutions] = useState<string[]>([""]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [mode, setMode] = useState<"ai" | "author_selected">("ai");
  const [umbrellas, setUmbrellas] = useState<Record<string, Umbrella[]>>({});
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!me) return;
    setChosen(me.home_communities.map((c) => `${c.level}:${c.entity_id}`).slice(0, 1));
  }, [me]);

  useEffect(() => {
    for (const key of chosen) {
      if (umbrellas[key]) continue;
      void get<{ umbrellas: Umbrella[] }>(`/umbrellas?community=${key}`)
        .then((body) => setUmbrellas((prev) => ({ ...prev, [key]: body.umbrellas })))
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen]);

  if (loading) return <Loading what="the form" />;
  if (!me) {
    return (
      <div className="mx-auto max-w-md px-4 py-8">
        <Notice>
          <Link href="/login">Sign in</Link> to write down a problem.
        </Notice>
      </div>
    );
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = await post<{ id: number; message: string }>("/posts", {
        problem_text: problem,
        solutions: solutions.map((s) => s.trim()).filter(Boolean),
        communities: chosen.map((key) => {
          const [level, entityId] = key.split(":");
          const umbrellaId = picked[key];
          return {
            level,
            entity_id: Number(entityId),
            umbrella_id:
              mode === "author_selected" && umbrellaId ? Number(umbrellaId) : null,
          };
        }),
        category_choice: mode,
      });
      router.push(`/posts/${body.id}`);
    } catch (problemRaised) {
      setError(
        problemRaised instanceof ApiError
          ? problemRaised.message
          : "Something went wrong.",
      );
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Write down a problem"
        lead="And say what you think should be done about it. Nothing can be posted here without at least one proposed solution."
      />
      <div className="mx-auto max-w-2xl px-4 py-8">
        {error ? <Notice kind="bad">{error}</Notice> : null}
        <form onSubmit={submit}>
          <Section title="1. The problem" description="What is wrong, where, and who it affects. Between 20 and 5,000 characters.">
            <label htmlFor="problem" className="sr-only">The problem</label>
            <textarea
              id="problem"
              required
              minLength={20}
              maxLength={5000}
              rows={6}
              className="field"
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
            />
            <p className="mt-1 text-sm text-[var(--muted)]">
              {problem.trim().length} characters. This cannot be edited once posted —
              it is fingerprinted when it is created.
            </p>
          </Section>

          <Section title="2. What should be done" description="At least one. Each becomes something your neighbours can support, improve, and eventually vote on.">
            <ol className="space-y-3">
              {solutions.map((text, index) => (
                <li key={index}>
                  <label htmlFor={`solution-${index}`} className="block font-medium">
                    Solution {index + 1}
                  </label>
                  <textarea
                    id={`solution-${index}`}
                    required={index === 0}
                    minLength={index === 0 ? 20 : undefined}
                    maxLength={5000}
                    rows={3}
                    className="field mt-1"
                    value={text}
                    onChange={(e) => {
                      const next = [...solutions];
                      next[index] = e.target.value;
                      setSolutions(next);
                    }}
                  />
                  {solutions.length > 1 ? (
                    <button
                      type="button"
                      className="btn mt-1 px-2 py-1 text-sm"
                      onClick={() => setSolutions(solutions.filter((_, i) => i !== index))}
                    >
                      Remove solution {index + 1}
                    </button>
                  ) : null}
                </li>
              ))}
            </ol>
            <button
              type="button"
              className="btn mt-3"
              onClick={() => setSolutions([...solutions, ""])}
            >
              Add another solution
            </button>
          </Section>

          <Section
            title="3. Which communities"
            description="You can post in your city, your county, and California. Each community works on it separately, with its own votes."
          >
            <fieldset className="space-y-2">
              <legend className="sr-only">Communities</legend>
              {me.home_communities.map((community) => {
                const key = `${community.level}:${community.entity_id}`;
                return (
                  <label key={key} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={chosen.includes(key)}
                      onChange={(e) =>
                        setChosen(
                          e.target.checked
                            ? [...chosen, key]
                            : chosen.filter((c) => c !== key),
                        )
                      }
                    />
                    <span>{community.label}</span>
                  </label>
                );
              })}
            </fieldset>
          </Section>

          <Section title="4. Where it gets filed">
            <fieldset className="space-y-2">
              <legend className="sr-only">How this gets filed</legend>
              <label className="flex items-start gap-2 rounded-lg border border-[var(--line)] p-3">
                <input
                  type="radio"
                  name="mode"
                  className="mt-1"
                  checked={mode === "ai"}
                  onChange={() => setMode("ai")}
                />
                <span>
                  <span className="font-medium">Let the platform file it</span>
                  <span className="block text-sm text-[var(--muted)]">
                    An AI model reads your problem and picks the closest umbrella
                    in each community. It is labelled as AI-filed, it is written
                    into the public log, and you can correct it afterwards.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 rounded-lg border border-[var(--line)] p-3">
                <input
                  type="radio"
                  name="mode"
                  className="mt-1"
                  checked={mode === "author_selected"}
                  onChange={() => setMode("author_selected")}
                />
                <span>
                  <span className="font-medium">I will pick the umbrella myself</span>
                  <span className="block text-sm text-[var(--muted)]">
                    No AI is involved at all.
                  </span>
                </span>
              </label>
            </fieldset>

            {mode === "author_selected" ? (
              <div className="mt-3 space-y-3">
                {chosen.map((key) => {
                  const community = me.home_communities.find(
                    (c) => `${c.level}:${c.entity_id}` === key,
                  );
                  return (
                    <div key={key}>
                      <label htmlFor={`umbrella-${key}`} className="block font-medium">
                        Umbrella in {community?.label}
                      </label>
                      <select
                        id={`umbrella-${key}`}
                        required
                        className="field mt-1"
                        value={picked[key] ?? ""}
                        onChange={(e) => setPicked({ ...picked, [key]: e.target.value })}
                      >
                        <option value="">Choose an umbrella</option>
                        {(umbrellas[key] ?? []).map((umbrella) => (
                          <option key={umbrella.id} value={umbrella.id}>
                            {umbrella.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </Section>

          <button
            type="submit"
            className="btn btn-primary mt-6"
            disabled={busy || !chosen.length || !me.email_verified}
          >
            {busy ? "Posting…" : "Post this"}
          </button>
          {!me.email_verified ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              Confirm your email address first — the link is in the message we
              sent when you signed up.
            </p>
          ) : null}
        </form>
      </div>
    </>
  );
}
