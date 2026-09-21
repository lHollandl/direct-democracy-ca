"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, get, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Loading, Notice, PageHeader, Section } from "@/components/ui";
import { UnverifiedEmailNotice } from "@/components/UnverifiedEmailNotice";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Umbrella = { id: number; name: string; statement: string };

type PreviewCommunity = {
  level: string;
  entity_id: number;
  umbrella_id: number | null;
  umbrella_name: string | null;
  active_umbrellas: Umbrella[];
};

type PreviewResult = {
  preview_id: number;
  main_category_id: number | null;
  main_category: string;
  confidence: number | null;
  communities: PreviewCommunity[];
};

type Decision = { choice: "keep" | "change" | "none"; umbrella_id: number | null };

const STEP_NAMES = ["The problem", "What should be done", "Which communities", "Where it goes"];
const MIN_PROBLEM = 20;
const MAX_PROBLEM = 5000;

function communityKey(level: string, entityId: number): string {
  return `${level}:${entityId}`;
}

/** DEMOCRACY.md §4.1 — a city by its name, a county as "<name> County", the
 * state as "California". Deliberately not the same string the rest of the
 * site uses (which appends "(city)"). */
function communityDisplayName(community: { level: string; name: string }): string {
  if (community.level === "city") return community.name;
  if (community.level === "county") return `${community.name} County`;
  return "California";
}

function draftSignature(problem: string, chosen: string[]): string {
  return JSON.stringify({ problem: problem.trim(), chosen: [...chosen].sort() });
}

export default function NewPostPage() {
  useDocumentTitle("Write down a problem");
  const router = useRouter();
  const { me, loading } = useSession();

  const [step, setStep] = useState(1);
  const [problem, setProblem] = useState("");
  const [solutions, setSolutions] = useState<string[]>([""]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [stepError, setStepError] = useState<string | null>(null);

  const [previewStatus, setPreviewStatus] = useState<
    "idle" | "loading" | "ready" | "unavailable" | "rate_limited"
  >("idle");
  const [previewMessage, setPreviewMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewSignature, setPreviewSignature] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});

  const [fallback, setFallback] = useState<"choose_myself" | "post_now" | null>(null);
  const [fallbackUmbrellas, setFallbackUmbrellas] = useState<Record<string, Umbrella[]>>({});
  const [fallbackPicked, setFallbackPicked] = useState<Record<string, string>>({});

  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const stale = previewSignature !== null && previewSignature !== draftSignature(problem, chosen);

  async function runPreview() {
    setPreviewStatus("loading");
    setPreviewMessage(null);
    setFallback(null);
    try {
      const body = await post<PreviewResult>("/posts/label-preview", {
        problem_text: problem.trim(),
        communities: chosen.map((key) => {
          const [level, entityId] = key.split(":");
          return { level, entity_id: Number(entityId) };
        }),
      });
      setPreview(body);
      setPreviewSignature(draftSignature(problem, chosen));
      setPreviewStatus("ready");
      setDecisions({});
    } catch (problemRaised) {
      if (problemRaised instanceof ApiError && problemRaised.status === 429) {
        setPreviewStatus("rate_limited");
        setPreviewMessage(problemRaised.message);
      } else {
        setPreviewStatus("unavailable");
        setPreviewMessage(
          problemRaised instanceof ApiError
            ? problemRaised.message
            : "The AI could not be reached just now.",
        );
      }
    }
  }

  useEffect(() => {
    if (step === 4 && previewStatus === "idle") {
      void runPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  useEffect(() => {
    if (fallback !== "choose_myself") return;
    for (const key of chosen) {
      if (fallbackUmbrellas[key]) continue;
      void get<{ umbrellas: Umbrella[] }>(`/umbrellas?community=${key}`)
        .then((body) => setFallbackUmbrellas((prev) => ({ ...prev, [key]: body.umbrellas })))
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fallback, chosen]);

  function goTo(next: number) {
    setStepError(null);
    clear();
    setStep(next);
  }

  function next() {
    if (step === 1) {
      const length = problem.trim().length;
      if (length < MIN_PROBLEM || length > MAX_PROBLEM) {
        setStepError(`Describe the problem in between ${MIN_PROBLEM} and ${MAX_PROBLEM.toLocaleString()} characters.`);
        return;
      }
    }
    if (step === 2) {
      const first = solutions[0]?.trim() ?? "";
      if (first.length < MIN_PROBLEM) {
        setStepError("At least one proposed solution, at least 20 characters.");
        return;
      }
    }
    if (step === 3 && chosen.length === 0) {
      setStepError("Choose at least one of your communities.");
      return;
    }
    goTo(step + 1);
  }

  const allDecided =
    previewStatus === "ready" &&
    !stale &&
    preview !== null &&
    preview.communities.every((c) => decisions[communityKey(c.level, c.entity_id)]);

  const fallbackReady =
    fallback === "post_now" ||
    (fallback === "choose_myself" && chosen.every((key) => fallbackPicked[key]));

  const canSubmit = allDecided || fallbackReady;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    if (!canSubmit) return;
    setBusy(true);
    const cleanedSolutions = solutions.map((s) => s.trim()).filter(Boolean);
    try {
      let payload: Record<string, unknown>;
      if (fallback === "post_now") {
        payload = {
          problem_text: problem.trim(),
          solutions: cleanedSolutions,
          communities: chosen.map((key) => {
            const [level, entityId] = key.split(":");
            return { level, entity_id: Number(entityId) };
          }),
          category_choice: "ai",
        };
      } else if (fallback === "choose_myself") {
        payload = {
          problem_text: problem.trim(),
          solutions: cleanedSolutions,
          communities: chosen.map((key) => {
            const [level, entityId] = key.split(":");
            return {
              level,
              entity_id: Number(entityId),
              umbrella_id: Number(fallbackPicked[key]),
            };
          }),
          category_choice: "author_selected",
        };
      } else if (preview) {
        payload = {
          problem_text: problem.trim(),
          solutions: cleanedSolutions,
          communities: preview.communities.map((c) => {
            const key = communityKey(c.level, c.entity_id);
            const decision = decisions[key];
            return {
              level: c.level,
              entity_id: c.entity_id,
              umbrella_id: decision.choice === "none" ? null : decision.umbrella_id,
            };
          }),
          category_choice: "preview",
          preview_id: preview.preview_id,
          main_category_id: preview.main_category_id,
        };
      } else {
        return;
      }
      const body = await post<{ id: number; message: string }>("/posts", payload);
      router.push(`/posts/${body.id}`);
    } catch (problemRaised) {
      fail(problemRaised, formRef.current);
      setBusy(false);
    }
  }

  let body: ReactNode;
  if (loading) {
    body = <Loading what="the form" />;
  } else if (!me) {
    body = (
      <Notice>
        <Link href="/login">Sign in</Link> to write down a problem.
      </Notice>
    );
  } else {
    const you = me;
    const isUnincorporated = you.home_communities.length === 2;

    body = (
      <>
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}
        <ol className="mb-6 flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Steps">
          {STEP_NAMES.map((name, index) => (
            <li
              key={name}
              aria-current={step === index + 1 ? "step" : undefined}
              className={step === index + 1 ? "font-bold" : "text-[var(--muted)]"}
            >
              {index + 1}. {name}
            </li>
          ))}
        </ol>

        <form ref={formRef} onSubmit={submit} noValidate>
          {step === 1 && !you.email_verified ? (
            <Notice kind="bad">
              <UnverifiedEmailNotice />
            </Notice>
          ) : null}

          {step === 1 ? (
            <Section
              title="1. The problem"
              description="What is wrong, where, and who it affects. Between 20 and 5,000 characters."
            >
              <label htmlFor="problem" className="sr-only">The problem</label>
              <textarea
                id="problem"
                name="problem_text"
                required
                minLength={MIN_PROBLEM}
                maxLength={MAX_PROBLEM}
                rows={6}
                className="field"
                value={problem}
                onChange={(e) => setProblem(e.target.value)}
                {...fieldProps("problem_text", "problem-hint")}
              />
              <FieldError name="problem_text" fieldErrors={fieldErrors} />
              <p id="problem-hint" className="mt-1 text-sm text-[var(--muted)]">
                {problem.trim().length} characters. This cannot be edited once posted —
                it is fingerprinted when it is created.
              </p>
            </Section>
          ) : null}

          {step === 2 ? (
            <Section
              title="2. What should be done"
              description="At least one. Each becomes something your neighbours can support, improve, and eventually vote on."
            >
              <ol className="space-y-3">
                {solutions.map((text, index) => (
                  <li key={index}>
                    <label htmlFor={`solution-${index}`} className="block font-medium">
                      Solution {index + 1}
                    </label>
                    <textarea
                      id={`solution-${index}`}
                      required={index === 0}
                      minLength={index === 0 ? MIN_PROBLEM : undefined}
                      maxLength={MAX_PROBLEM}
                      rows={3}
                      className="field mt-1"
                      value={text}
                      onChange={(e) => {
                        const nextSolutions = [...solutions];
                        nextSolutions[index] = e.target.value;
                        setSolutions(nextSolutions);
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
              <button type="button" className="btn mt-3" onClick={() => setSolutions([...solutions, ""])}>
                Add another solution
              </button>
            </Section>
          ) : null}

          {step === 3 ? (
            <Section
              title="3. Which communities"
              description="You can post in your city, your county, and California. Each community works on it separately, with its own votes."
            >
              <fieldset className="space-y-2">
                <legend className="sr-only">Communities</legend>
                {you.home_communities.map((community) => {
                  const key = communityKey(community.level, community.entity_id);
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
                      <span>{communityDisplayName(community)}</span>
                    </label>
                  );
                })}
                <label className="flex items-center gap-2 text-[var(--muted)]" aria-disabled="true">
                  <input type="checkbox" disabled aria-disabled="true" />
                  <span>Federal — planned, not yet available</span>
                </label>
              </fieldset>
              {isUnincorporated ? (
                <p className="mt-3 text-sm text-[var(--muted)]">
                  You live in an unincorporated area, so you have no city
                  community. Your posts go to your county and California.
                </p>
              ) : null}
            </Section>
          ) : null}

          {step === 4 ? (
            <Section title="4. Where it goes">
              {previewStatus === "loading" ? (
                <p role="status" className="text-sm text-[var(--muted)]">
                  The AI is reading your draft…
                </p>
              ) : null}

              {stale && previewStatus !== "loading" ? (
                <div className="mb-4">
                  <Notice>
                    Your draft changed since this suggestion ran. It is out of
                    date.
                  </Notice>
                  <button type="button" className="btn mt-2" onClick={() => void runPreview()}>
                    Get a fresh suggestion
                  </button>
                </div>
              ) : null}

              {(previewStatus === "unavailable" || previewStatus === "rate_limited") && !fallback ? (
                <div className="space-y-3">
                  <Notice kind="bad">
                    {previewMessage ??
                      "The AI could not be reached just now."}
                  </Notice>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="btn" onClick={() => setFallback("choose_myself")}>
                      Choose myself
                    </button>
                    <button type="button" className="btn" onClick={() => setFallback("post_now")}>
                      Post now, file later
                    </button>
                  </div>
                </div>
              ) : null}

              {previewStatus === "ready" && !stale && preview && !fallback ? (
                <div className="space-y-5">
                  <p className="text-sm text-[var(--muted)]">
                    Main category: <span className="font-medium text-[var(--fg)]">{preview.main_category}</span>
                  </p>
                  {preview.communities.map((c) => {
                    const key = communityKey(c.level, c.entity_id);
                    const community = you.home_communities.find(
                      (h) => h.level === c.level && h.entity_id === c.entity_id,
                    );
                    const decision = decisions[key];
                    return (
                      <fieldset key={key} className="rounded-lg border border-[var(--line)] p-3">
                        <legend className="px-1 font-medium">
                          {community ? communityDisplayName(community) : `${c.level} ${c.entity_id}`}
                        </legend>
                        <p className="text-sm text-[var(--muted)]">
                          {c.umbrella_name
                            ? <>Suggested: <span className="text-[var(--fg)]">{c.umbrella_name}</span></>
                            : "The AI found no umbrella here that fits."}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <label className="flex items-center gap-1">
                            <input
                              type="radio"
                              name={`decision-${key}`}
                              checked={decision?.choice === "keep"}
                              onChange={() =>
                                setDecisions({
                                  ...decisions,
                                  [key]: { choice: "keep", umbrella_id: c.umbrella_id },
                                })
                              }
                            />
                            {c.umbrella_name ? "Keep" : "Keep (none of these fit)"}
                          </label>
                          {c.active_umbrellas.length ? (
                            <label className="flex items-center gap-1">
                              <input
                                type="radio"
                                name={`decision-${key}`}
                                checked={decision?.choice === "change"}
                                onChange={() =>
                                  setDecisions({
                                    ...decisions,
                                    [key]: {
                                      choice: "change",
                                      umbrella_id: c.active_umbrellas[0]?.id ?? null,
                                    },
                                  })
                                }
                              />
                              Change
                            </label>
                          ) : null}
                          <label className="flex items-center gap-1">
                            <input
                              type="radio"
                              name={`decision-${key}`}
                              checked={decision?.choice === "none"}
                              onChange={() =>
                                setDecisions({
                                  ...decisions,
                                  [key]: { choice: "none", umbrella_id: null },
                                })
                              }
                            />
                            None of these fit
                          </label>
                        </div>
                        {decision?.choice === "change" ? (
                          <div className="mt-2">
                            <label htmlFor={`change-${key}`} className="sr-only">
                              Umbrella in {community ? communityDisplayName(community) : c.level}
                            </label>
                            <select
                              id={`change-${key}`}
                              className="field"
                              value={decision.umbrella_id ?? ""}
                              onChange={(e) =>
                                setDecisions({
                                  ...decisions,
                                  [key]: { choice: "change", umbrella_id: Number(e.target.value) },
                                })
                              }
                            >
                              {c.active_umbrellas.map((u) => (
                                <option key={u.id} value={u.id}>{u.name}</option>
                              ))}
                            </select>
                          </div>
                        ) : null}
                      </fieldset>
                    );
                  })}
                  <button type="button" className="btn" onClick={() => setFallback("choose_myself")}>
                    Choose myself instead
                  </button>
                </div>
              ) : null}

              {fallback === "choose_myself" ? (
                <div className="mt-3 space-y-3">
                  {chosen.map((key) => {
                    const community = you.home_communities.find(
                      (c) => communityKey(c.level, c.entity_id) === key,
                    );
                    return (
                      <div key={key}>
                        <label htmlFor={`umbrella-${key}`} className="block font-medium">
                          Umbrella in {community ? communityDisplayName(community) : key}
                        </label>
                        <select
                          id={`umbrella-${key}`}
                          required
                          className="field mt-1"
                          value={fallbackPicked[key] ?? ""}
                          onChange={(e) => setFallbackPicked({ ...fallbackPicked, [key]: e.target.value })}
                        >
                          <option value="">Choose an umbrella</option>
                          {(fallbackUmbrellas[key] ?? []).map((umbrella) => (
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
          ) : null}

          {stepError ? (
            <p role="alert" className="mt-3 text-sm" style={{ color: "var(--bad)" }}>
              {stepError}
            </p>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-2">
            {step > 1 ? (
              <button type="button" className="btn" onClick={() => goTo(step - 1)}>
                Back
              </button>
            ) : null}
            {step < 4 ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={next}
                disabled={!you.email_verified}
              >
                Next
              </button>
            ) : (
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy || !canSubmit || !you.email_verified}
              >
                {busy ? "Posting…" : "Post this"}
              </button>
            )}
          </div>
        </form>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Write down a problem"
        lead={
          me
            ? "And say what you think should be done about it. Nothing can be posted here without at least one proposed solution."
            : undefined
        }
      />
      <div className={`mx-auto px-4 py-8 ${me ? "max-w-2xl" : "max-w-md"}`}>{body}</div>
    </>
  );
}
