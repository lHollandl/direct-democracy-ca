"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { AiInfluence, BackLink, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Post = {
  id: number;
  title: string;
  problem_text: string;
  author: string;
  author_id: number;
  created_at: string;
  content_hash: string;
  label_status: string;
  ai_influence: { label: string; explanation: string };
  immutable_note: string;
  communities: {
    community: { level: string; entity_id: number; label: string };
    umbrella_id: number | null;
    umbrella_name: string | null;
    main_category: string | null;
    label_status: string;
    has_active_umbrella: boolean;
    label_shown_as: string | null;
    confidence: number | null;
    solution_ids: number[];
  }[];
  solution_texts: { id: number; position: number; text: string; content_hash: string }[];
};

type Umbrella = { id: number; name: string; statement: string };

export default function PostPage() {
  useDocumentTitle("A problem report");
  const { id } = useParams<{ id: string }>();
  const { me } = useSession();
  const [data, setData] = useState<Post | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [choices, setChoices] = useState<Record<string, Umbrella[]>>({});

  const load = useCallback(async () => {
    setData(await get<Post>(`/posts/${id}`));
  }, [id]);

  useEffect(() => {
    void load().catch(() => setData(null));
  }, [load]);

  useEffect(() => {
    if (!data) return;
    for (const row of data.communities) {
      const key = `${row.community.level}:${row.community.entity_id}`;
      if (choices[key]) continue;
      void get<{ umbrellas: Umbrella[] }>(`/umbrellas?community=${key}`)
        .then((body) => setChoices((prev) => ({ ...prev, [key]: body.umbrellas })))
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const isAuthor = data ? me?.id === data.author_id : false;

  async function confirm() {
    setError(null);
    try {
      const body = await post<{ message: string }>(`/posts/${id}/label/confirm`);
      setMessage(body.message);
      await load();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    }
  }

  async function correct(level: string, entityId: number, umbrellaId: number) {
    setError(null);
    try {
      const body = await post<{ note: string | null }>(`/posts/${id}/label/correct`, {
        level,
        entity_id: entityId,
        umbrella_id: umbrellaId,
      });
      setMessage(body.note ?? "Moved. Thank you — the correction is recorded.");
      await load();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    }
  }

  return (
    <>
      <PageHeader
        title={data?.title ?? "A problem report"}
        lead={data ? `Posted by ${data.author}` : undefined}
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        {!data ? (
          <Loading what="this post" />
        ) : (
          <>
        <BackLink href="/home">Back to Home</BackLink>
        {message ? <div className="mt-3"><Notice kind="good">{message}</Notice></div> : null}
        {error ? <div className="mt-3"><Notice kind="bad">{error}</Notice></div> : null}

        <Section title="The problem">
          <p className="whitespace-pre-line">{data.problem_text}</p>
          <p className="mt-2 break-all text-xs text-[var(--muted)]">
            Fingerprint: {data.content_hash}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">{data.immutable_note}</p>
          <AiInfluence influence={data.ai_influence} />
        </Section>

        <Section title="What the author proposed">
          <ol className="space-y-3">
            {data.solution_texts.map((solution) => (
              <li key={solution.id} className="card p-3">
                <p className="whitespace-pre-line">{solution.text}</p>
                <p className="mt-2 break-all text-xs text-[var(--muted)]">
                  Fingerprint: {solution.content_hash}
                </p>
              </li>
            ))}
          </ol>
        </Section>

        <Section
          title="Where this was filed"
          description="A problem is filed into one umbrella per community, so the people who can act on it find it."
        >
          <ul className="space-y-3">
            {data.communities.map((row) => {
              const key = `${row.community.level}:${row.community.entity_id}`;
              return (
                <li key={key} className="card p-3">
                  <p className="font-medium">{row.community.label}</p>
                  <p className="text-sm">
                    {row.umbrella_id ? (
                      <>
                        Filed under{" "}
                        <Link href={`/umbrellas/${row.umbrella_id}`}>{row.umbrella_name}</Link>
                      </>
                    ) : (
                      row.label_status
                    )}
                  </p>
                  {row.label_shown_as ? (
                    <p className="text-sm text-[var(--muted)]">
                      {row.label_shown_as}
                      {row.confidence !== null
                        ? ` · the model's own confidence: ${row.confidence}`
                        : ""}
                    </p>
                  ) : null}
                  {row.solution_ids.length ? (
                    <p className="mt-1 text-sm">
                      In the workshop:{" "}
                      {row.solution_ids.map((solutionId, index) => (
                        <span key={solutionId}>
                          {index > 0 ? ", " : ""}
                          <Link href={`/solutions/${solutionId}`}>solution {index + 1}</Link>
                        </span>
                      ))}
                    </p>
                  ) : null}

                  {isAuthor && row.has_active_umbrella ? (
                    <div className="mt-3 border-t border-[var(--line)] pt-3">
                      <p className="text-sm font-medium">Is that the right place?</p>
                      <div className="mt-2 flex flex-wrap items-end gap-2">
                        <button type="button" className="btn" onClick={() => void confirm()}>
                          Yes, that is right
                        </button>
                        <div>
                          <label
                            htmlFor={`move-${key}`}
                            className="block text-sm text-[var(--muted)]"
                          >
                            No — move it to
                          </label>
                          <select
                            id={`move-${key}`}
                            className="field mt-1"
                            defaultValue=""
                            onChange={(e) => {
                              if (e.target.value) {
                                void correct(
                                  row.community.level,
                                  row.community.entity_id,
                                  Number(e.target.value),
                                );
                              }
                            }}
                          >
                            <option value="">Choose an umbrella</option>
                            {(choices[key] ?? []).map((umbrella) => (
                              <option key={umbrella.id} value={umbrella.id}>
                                {umbrella.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  ) : isAuthor && !row.umbrella_id ? (
                    <div className="mt-3 border-t border-[var(--line)] pt-3">
                      <p className="text-sm text-[var(--muted)]">
                        There are no umbrellas in {row.community.label} yet. Proposing
                        a new umbrella is planned.
                      </p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Section>
          </>
        )}
      </div>
    </>
  );
}
