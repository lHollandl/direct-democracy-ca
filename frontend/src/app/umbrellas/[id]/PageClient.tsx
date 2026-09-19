"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { post, put, get } from "@/lib/api";
import { useSession } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import Comments, { Comment } from "@/components/Comments";
import VoteButtons from "@/components/VoteButtons";
import {
  AiInfluence,
  Badge,
  Empty,
  Explainer,
  Loading,
  Notice,
  PageHeader,
  Section,
} from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Solution = {
  id: number;
  text: string;
  version: number;
  author: string;
  net_score: number;
  my_vote: number | null;
  status_badge: string | null;
  is_dominant: boolean;
  on_track_for_ballot: boolean;
  last_ballot_result: string | null;
  ai_influence: { label: string; explanation: string };
};

type Amendment = {
  id: number;
  author: string;
  proposed_text: string;
  rationale: string;
  status: string;
  absorbed_as_version: number | null;
  net_score: number;
  my_vote: number | null;
  diff: { kind: string; text: string }[];
  ai_influence: { label: string; explanation: string };
};

type Dominant = {
  solution_id: number;
  text: string;
  version: number;
  net_score: number;
  supporters: number;
  absorption_threshold: number;
  amendments: Amendment[];
  similar_pairs: {
    id: number;
    amendment_a_id: number;
    amendment_b_id: number;
    score: number;
    decision: string;
    question: string;
    labelled: string;
  }[];
  discussion: Comment[];
};

type Reference = {
  id: number;
  url: string;
  title: string;
  why: string;
  label: string;
  status: string;
  useful: number;
  not_useful: number;
};

type Page = {
  problem: {
    id: number;
    name: string;
    statement: string;
    community: { level: string; entity_id: number; label: string };
    main_category: string | null;
    active_users: number;
    active_user_definition: string;
    ai_action_list: { sentence: string };
    dominant_threshold: number;
    ballot_threshold: number;
  };
  problem_reports: {
    post_id: number;
    title: string;
    problem_text: string;
    author: string;
    label_shown_as: string | null;
    ai_influence: { label: string; explanation: string };
  }[];
  problem_discussion: Comment[];
  solutions: Solution[];
  dominant_solutions: Dominant[];
  references: {
    active: Reference[];
    rejected: Reference[];
    note: string;
    recommending: boolean;
  };
  ordering: { version: string; explanation: string };
};

export default function UmbrellaPage() {
  useDocumentTitle("The workshop");
  const { id } = useParams<{ id: string }>();
  const { me } = useSession();
  const { error, alertRef, clear, fail } = useFormError();
  const { data, reload } = useLoader<Page>(() => get<Page>(`/umbrellas/${id}`), [id]);
  const load = reload;

  const isMember =
    !!data &&
    (me?.home_communities.some(
      (c) =>
        c.level === data.problem.community.level &&
        c.entity_id === data.problem.community.entity_id,
    ) ?? false);
  const canAct = isMember && (me?.email_verified ?? false);

  return (
    <>
      <PageHeader title={data?.problem.name ?? "The workshop"} lead={data?.problem.statement}>
        {data ? (
          <p className="mt-3 text-sm">
            {data.problem.community.label}
            {data.problem.main_category ? ` · ${data.problem.main_category}` : ""} ·{" "}
            {data.problem.active_users} active{" "}
            {data.problem.active_users === 1 ? "resident" : "residents"}
          </p>
        ) : null}
      </PageHeader>

      <div className="mx-auto max-w-3xl px-4 py-8">
        {!data ? (
          <Loading what="this workshop" />
        ) : (
          <>
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}
        {!isMember ? (
          <Notice>
            You can read everything here. Posting, commenting and voting happen
            in your own city, your county and California.
          </Notice>
        ) : null}

        <Explainer title="What these numbers mean">
          <p>{data.problem.active_user_definition}</p>
          <p className="mt-2">
            A solution becomes <strong>dominant</strong> — open to amendment and
            discussion — at a net score of {data.problem.dominant_threshold}. It
            is on track for the ballot at {data.problem.ballot_threshold}. Both
            numbers come from the{" "}
            <Link href="/settings">public settings</Link>.
          </p>
        </Explainer>

        <Explainer title={data.problem.ai_action_list.sentence}>
          <p>
            Every one of those actions is in the{" "}
            <Link href={`/ai/actions?subject_type=umbrella&subject_id=${data.problem.id}`}>
              public AI log
            </Link>
            . AI sorts and suggests here. It never decides.
          </p>
        </Explainer>

        <Section
          title="Problem reports"
          description="What people wrote when they filed a problem here. Newest first."
        >
          {data.problem_reports.length === 0 ? (
            <Empty>Nobody has filed a problem here yet.</Empty>
          ) : (
            <ol className="space-y-3">
              {data.problem_reports.map((report) => (
                <li key={report.post_id} className="card p-3">
                  <p className="whitespace-pre-line">{report.problem_text}</p>
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    {report.author}
                    {report.label_shown_as ? ` · ${report.label_shown_as}` : ""} ·{" "}
                    <Link href={`/posts/${report.post_id}`}>the post</Link>
                  </p>
                  <AiInfluence influence={report.ai_influence} />
                </li>
              ))}
            </ol>
          )}
        </Section>

        <Section title="Discussion of the problem">
          <Comments
            targetType="umbrella"
            targetId={data.problem.id}
            comments={data.problem_discussion}
            canWrite={canAct}
            onPosted={() => load()}
          />
        </Section>

        <Section title="Solutions" description={data.ordering.explanation}>
          {canAct ? <AddSolution umbrellaId={data.problem.id} onAdded={() => load()} /> : null}
          {data.solutions.length === 0 ? (
            <Empty>No solutions here yet.</Empty>
          ) : (
            <ol className="mt-3 space-y-3">
              {data.solutions.map((solution) => (
                <li key={solution.id} className="card p-3">
                  <p className="whitespace-pre-line">{solution.text}</p>
                  <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
                    <span>{solution.author}</span>
                    <span>· version {solution.version}</span>
                    {solution.status_badge ? <Badge>{solution.status_badge}</Badge> : null}
                    {solution.on_track_for_ballot ? <Badge>on track for the ballot</Badge> : null}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    {canAct ? (
                      <VoteButtons
                        targetType="solution"
                        targetId={solution.id}
                        netScore={solution.net_score}
                        myVote={solution.my_vote}
                        label={`the solution by ${solution.author}`}
                        onChanged={() => load()}
                      />
                    ) : (
                      <span className="font-bold">Net score {solution.net_score}</span>
                    )}
                    <Link href={`/solutions/${solution.id}`} className="text-sm">
                      Open this solution
                    </Link>
                  </div>
                  <AiInfluence influence={solution.ai_influence} />
                </li>
              ))}
            </ol>
          )}
        </Section>

        <Section
          title="Dominant solutions"
          description="These have enough support to be worth working on, so they can be amended and discussed. Everything else, you support or you propose a better one."
        >
          {data.dominant_solutions.length === 0 ? (
            <Empty>Nothing is dominant here yet.</Empty>
          ) : (
            <div className="space-y-6">
              {data.dominant_solutions.map((dominant) => (
                <article key={dominant.solution_id} className="card p-4">
                  <p className="whitespace-pre-line font-medium">{dominant.text}</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Version {dominant.version} · {dominant.supporters}{" "}
                    {dominant.supporters === 1 ? "supporter" : "supporters"} · an
                    amendment is absorbed at a net score of{" "}
                    {dominant.absorption_threshold}
                  </p>

                  <h3 className="mt-4 font-bold">Amendments</h3>
                  {canAct ? (
                    <ProposeAmendment
                      solutionId={dominant.solution_id}
                      onProposed={() => load()}
                    />
                  ) : null}
                  {dominant.amendments.length === 0 ? (
                    <p className="mt-2 text-sm text-[var(--muted)]">
                      Nobody has proposed a change yet.
                    </p>
                  ) : (
                    <ol className="mt-3 space-y-3">
                      {dominant.amendments.map((amendment) => (
                        <li key={amendment.id} className="rounded-lg border border-[var(--line)] p-3">
                          <p className="text-sm font-medium">
                            {amendment.author} · <Badge>{amendment.status.replace("_", " ")}</Badge>
                            {amendment.absorbed_as_version
                              ? ` · became version ${amendment.absorbed_as_version}`
                              : ""}
                          </p>
                          <p className="mt-1 text-sm italic">“{amendment.rationale}”</p>
                          <AiInfluence influence={amendment.ai_influence} />
                          <p className="mt-2 text-sm">
                            {amendment.diff.map((part, index) => (
                              <span
                                key={index}
                                className={
                                  part.kind === "added"
                                    ? "bg-[#e3f3e8] font-medium"
                                    : part.kind === "removed"
                                      ? "bg-[#f7e3e3] line-through"
                                      : ""
                                }
                              >
                                {part.kind === "added" ? "[added] " : part.kind === "removed" ? "[removed] " : ""}
                                {part.text}{" "}
                              </span>
                            ))}
                          </p>
                          {canAct && amendment.status === "proposed" ? (
                            <div className="mt-2">
                              <VoteButtons
                                targetType="amendment"
                                targetId={amendment.id}
                                netScore={amendment.net_score}
                                myVote={amendment.my_vote}
                                label={`the amendment by ${amendment.author}`}
                                onChanged={() => load()}
                              />
                            </div>
                          ) : (
                            <p className="mt-2 text-sm font-bold">
                              Net score {amendment.net_score}
                            </p>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}

                  {dominant.similar_pairs.filter((p) => p.decision === "pending").length ? (
                    <div className="mt-4 rounded-lg border border-[var(--accent)] p-3">
                      <h4 className="font-bold">AI thinks two of these are the same change</h4>
                      {dominant.similar_pairs
                        .filter((pair) => pair.decision === "pending")
                        .map((pair) => (
                          <div key={pair.id} className="mt-2">
                            <p className="text-sm">
                              {pair.question} <span className="text-[var(--muted)]">({pair.labelled})</span>
                            </p>
                            {canAct ? (
                              <div className="mt-1 flex gap-2">
                                {(["same", "different"] as const).map((choice) => (
                                  <button
                                    key={choice}
                                    type="button"
                                    className="btn px-3 py-1 text-sm"
                                    onClick={async () => {
                                      clear();
                                      try {
                                        await post(`/similarity/${pair.id}/decide`, { choice });
                                        load();
                                      } catch (problem) {
                                        fail(problem);
                                      }
                                    }}
                                  >
                                    {choice === "same" ? "Same change" : "Different change"}
                                  </button>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))}
                    </div>
                  ) : null}

                  <h3 className="mt-4 font-bold">Discussion</h3>
                  <Comments
                    targetType="solution"
                    targetId={dominant.solution_id}
                    comments={dominant.discussion}
                    canWrite={canAct}
                    onPosted={() => load()}
                  />
                </article>
              ))}
            </div>
          )}
        </Section>

        <Section title="References" description={data.references.note}>
          {data.references.recommending ? (
            <Notice>AI is looking for references…</Notice>
          ) : null}
          {canAct ? <AddReference umbrellaId={data.problem.id} onAdded={() => load()} /> : null}
          {data.references.active.length === 0 && data.references.rejected.length === 0 ? (
            <Empty>Nobody has added anything to read yet.</Empty>
          ) : (
            <>
              <ul className="mt-3 space-y-2">
                {data.references.active.map((reference) => (
                  <li key={reference.id} className="card p-3">
                    <a href={reference.url} className="font-medium">{reference.title}</a>
                    <p className="text-sm">{reference.why}</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{reference.label}</p>
                    {canAct ? (
                      <div className="mt-2 flex gap-2">
                        {[true, false].map((useful) => (
                          <button
                            key={String(useful)}
                            type="button"
                            className="btn px-3 py-1 text-sm"
                            onClick={async () => {
                              await put(`/references/${reference.id}/feedback`, { useful });
                              load();
                            }}
                          >
                            {useful
                              ? `Useful (${reference.useful})`
                              : `Not useful (${reference.not_useful})`}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
              {data.references.rejected.length ? (
                <details className="mt-3">
                  <summary className="cursor-pointer text-sm font-medium">
                    Rejected references ({data.references.rejected.length}) — kept, never deleted
                  </summary>
                  <ul className="mt-2 space-y-2">
                    {data.references.rejected.map((reference) => (
                      <li key={reference.id} className="card p-3 opacity-70">
                        <a href={reference.url}>{reference.title}</a>
                        <p className="text-sm">{reference.why}</p>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </>
          )}
        </Section>
          </>
        )}
      </div>
    </>
  );
}

function AddSolution({ umbrellaId, onAdded }: { umbrellaId: number; onAdded: () => void }) {
  const [text, setText] = useState("");
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [open, setOpen] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  if (!open) {
    return (
      <button type="button" className="btn" onClick={() => setOpen(true)}>
        Propose a solution
      </button>
    );
  }
  return (
    <form
      ref={formRef}
      className="card p-3"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault();
        clear();
        try {
          await post(`/umbrellas/${umbrellaId}/solutions`, { text });
          setText("");
          setOpen(false);
          onAdded();
        } catch (problem) {
          fail(problem, formRef.current);
        }
      }}
    >
      <label htmlFor="new-solution" className="block font-medium">
        What should be done about this problem?
      </label>
      <textarea
        id="new-solution"
        name="text"
        className="field mt-1"
        rows={4}
        required
        minLength={20}
        maxLength={5000}
        value={text}
        onChange={(e) => setText(e.target.value)}
        {...fieldProps("text", "new-solution-hint")}
      />
      <FieldError name="text" fieldErrors={fieldErrors} />
      <p id="new-solution-hint" className="mt-1 text-sm text-[var(--muted)]">
        Once posted this belongs to the community: when it becomes dominant,
        anyone here can propose a change to it.
      </p>
      {error ? (
        <div className="mt-1">
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        </div>
      ) : null}
      <div className="mt-2 flex gap-2">
        <button type="submit" className="btn btn-primary">Post it</button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}

function ProposeAmendment({
  solutionId,
  onProposed,
}: {
  solutionId: number;
  onProposed: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [rationale, setRationale] = useState("");
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const formRef = useRef<HTMLFormElement>(null);

  if (!open) {
    return (
      <button type="button" className="btn mt-2" onClick={() => setOpen(true)}>
        Propose a change
      </button>
    );
  }
  return (
    <form
      ref={formRef}
      className="mt-2 rounded-lg border border-[var(--line)] p-3"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault();
        clear();
        try {
          await post(`/solutions/${solutionId}/amendments`, {
            proposed_text: text,
            rationale,
          });
          setText("");
          setRationale("");
          setOpen(false);
          onProposed();
        } catch (problem) {
          fail(problem, formRef.current);
        }
      }}
    >
      {error ? (
        <Notice kind="bad" alertRef={alertRef}>
          {error}
        </Notice>
      ) : null}
      <label htmlFor={`amend-${solutionId}`} className="block font-medium">
        The whole solution, as you would have it read
      </label>
      <textarea
        id={`amend-${solutionId}`}
        name="proposed_text"
        className="field mt-1"
        rows={4}
        required
        minLength={20}
        maxLength={5000}
        value={text}
        onChange={(e) => setText(e.target.value)}
        {...fieldProps("proposed_text")}
      />
      <FieldError name="proposed_text" fieldErrors={fieldErrors} />
      <label htmlFor={`why-${solutionId}`} className="mt-3 block font-medium">
        Why, in one line
      </label>
      <input
        id={`why-${solutionId}`}
        name="rationale"
        className="field mt-1"
        required
        minLength={10}
        maxLength={300}
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        {...fieldProps("rationale")}
      />
      <FieldError name="rationale" fieldErrors={fieldErrors} />
      <div className="mt-2 flex gap-2">
        <button type="submit" className="btn btn-primary">Propose it</button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}

function AddReference({ umbrellaId, onAdded }: { umbrellaId: number; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const formRef = useRef<HTMLFormElement>(null);

  if (!open) {
    return (
      <button type="button" className="btn" onClick={() => setOpen(true)}>
        Add something worth reading
      </button>
    );
  }
  return (
    <form
      ref={formRef}
      className="card p-3"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault();
        clear();
        const form = new FormData(event.currentTarget);
        try {
          await post(`/umbrellas/${umbrellaId}/references`, {
            url: form.get("url"),
            title: form.get("title"),
            note: form.get("note"),
          });
          setOpen(false);
          onAdded();
        } catch (problem) {
          fail(problem, formRef.current);
        }
      }}
    >
      <label htmlFor="ref-url" className="block font-medium">Web address</label>
      <input
        id="ref-url"
        name="url"
        type="url"
        required
        className="field mt-1"
        {...fieldProps("url")}
      />
      <FieldError name="url" fieldErrors={fieldErrors} />
      <label htmlFor="ref-title" className="mt-2 block font-medium">What it is called</label>
      <input id="ref-title" name="title" className="field mt-1" {...fieldProps("title")} />
      <FieldError name="title" fieldErrors={fieldErrors} />
      <label htmlFor="ref-note" className="mt-2 block font-medium">Why it is worth reading</label>
      <input
        id="ref-note"
        name="note"
        required
        maxLength={300}
        className="field mt-1"
        {...fieldProps("note")}
      />
      <FieldError name="note" fieldErrors={fieldErrors} />
      {error ? (
        <div className="mt-1">
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        </div>
      ) : null}
      <div className="mt-2 flex gap-2">
        <button type="submit" className="btn btn-primary">Add it</button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}
