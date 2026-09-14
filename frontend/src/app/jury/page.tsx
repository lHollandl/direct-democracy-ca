"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, get, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import { Badge, Empty, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Item = {
  ballot_item_id: number;
  position: number;
  umbrella: string | null;
  frozen_text: string;
  frozen_version: number;
  net_score_at_snapshot: number;
  amendment_history: { id: number; rationale: string; status: string }[];
  previous_holdback_reasons: { category: string; reason: string }[];
  my_holdback: { category: string; reason: string } | null;
  reason_categories: string[];
};

type Duty = {
  juror_id: number;
  seat: number;
  status: string;
  cycle_id: number;
  cycle_number: number;
  cycle_state: string;
  community: { label: string };
  what_you_can_do: string;
  items: Item[];
};

const CATEGORY_WORDS: Record<string, string> = {
  duplicate: "It duplicates something else",
  not_actionable: "Nobody could actually do this",
  incomplete: "Important details are missing",
  outside_governance_level: "This is not something this level of government decides",
  other: "Something else",
};

export default function JuryPage() {
  useDocumentTitle("Jury duty");
  const { me, loading } = useSession();
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: duties, reload } = useLoader<Duty[]>(async () => {
    if (!me) return [];
    try {
      return (await get<{ duties: Duty[] }>("/juries/mine")).duties;
    } catch {
      return [];
    }
  }, [me]);

  if (loading) return <Loading what="your jury duty" />;
  if (!me) {
    return (
      <div className="mx-auto max-w-md px-4 py-8">
        <Notice>
          <Link href="/login">Sign in</Link> to see whether you have been drawn.
        </Notice>
      </div>
    );
  }
  if (duties === null) return <Loading what="your jury duty" />;

  async function answer(jurorId: number, choice: "accept" | "decline") {
    setError(null);
    try {
      const body = await post<{ message?: string; note?: string }>(
        `/jurors/${jurorId}/${choice}`,
      );
      setNote(body.message ?? body.note ?? null);
      reload();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    }
  }

  return (
    <>
      <PageHeader
        title="Jury duty"
        lead="Before a ballot opens, a few residents drawn at random look over what qualified. You cannot change anything. You can hold something back, in public, with a reason."
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        {note ? <Notice kind="good">{note}</Notice> : null}
        {error ? <Notice kind="bad">{error}</Notice> : null}
        {duties.length === 0 ? (
          <Empty>You have not been drawn for a jury.</Empty>
        ) : (
          duties.map((duty) => (
            <Section
              key={duty.juror_id}
              title={`${duty.community.label} — cycle ${duty.cycle_number}`}
              description={duty.what_you_can_do}
            >
              <p className="text-sm">
                You are juror {duty.seat}. Your answer so far:{" "}
                <Badge>{duty.status.replace("_", " ")}</Badge>
              </p>
              {duty.status === "drawn" ? (
                <div className="mt-3 flex gap-2">
                  <button type="button" className="btn btn-primary" onClick={() => void answer(duty.juror_id, "accept")}>
                    I will do it
                  </button>
                  <button type="button" className="btn" onClick={() => void answer(duty.juror_id, "decline")}>
                    I cannot — draw somebody else
                  </button>
                </div>
              ) : null}

              {duty.items.map((item) => (
                <article key={item.ballot_item_id} className="card mt-4 p-4">
                  <p className="text-sm font-medium">
                    {item.position}. {item.umbrella}
                  </p>
                  <p className="mt-1 whitespace-pre-line">{item.frozen_text}</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Version {item.frozen_version} · net score at the snapshot{" "}
                    {item.net_score_at_snapshot}
                  </p>
                  {item.amendment_history.length ? (
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer">How it got here</summary>
                      <ul className="mt-1 list-disc pl-5">
                        {item.amendment_history.map((amendment) => (
                          <li key={amendment.id}>
                            {amendment.rationale} ({amendment.status.replace("_", " ")})
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  {item.previous_holdback_reasons.length ? (
                    <div className="mt-2 rounded-lg border border-[var(--line)] p-2 text-sm">
                      <p className="font-medium">A previous jury held this back:</p>
                      <ul className="mt-1 list-disc pl-5">
                        {item.previous_holdback_reasons.map((reason, index) => (
                          <li key={index}>
                            {CATEGORY_WORDS[reason.category] ?? reason.category}: {reason.reason}
                          </li>
                        ))}
                      </ul>
                      <p className="mt-1 text-[var(--muted)]">
                        You are free to hold the new version back again, for any
                        reason.
                      </p>
                    </div>
                  ) : null}

                  {item.my_holdback ? (
                    <Notice kind="good">
                      You held this back: {item.my_holdback.reason}
                    </Notice>
                  ) : duty.status === "accepted" && duty.cycle_state === "jury_review" ? (
                    <HoldbackForm
                      itemId={item.ballot_item_id}
                      jurorId={duty.juror_id}
                      categories={item.reason_categories}
                      onDone={reload}
                      onError={setError}
                    />
                  ) : null}
                </article>
              ))}
            </Section>
          ))
        )}
      </div>
    </>
  );
}

function HoldbackForm({
  itemId,
  jurorId,
  categories,
  onDone,
  onError,
}: {
  itemId: number;
  jurorId: number;
  categories: string[];
  onDone: () => void;
  onError: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button type="button" className="btn mt-3" onClick={() => setOpen(true)}>
        Hold this back
      </button>
    );
  }
  return (
    <form
      className="mt-3 rounded-lg border border-[var(--line)] p-3"
      onSubmit={async (event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        try {
          await post(`/ballot-items/${itemId}/holdback`, {
            juror_id: jurorId,
            reason_category: form.get("category"),
            reason_text: form.get("reason"),
          });
          setOpen(false);
          onDone();
        } catch (problem) {
          onError(problem instanceof ApiError ? problem.message : "Something went wrong.");
        }
      }}
    >
      <label htmlFor={`cat-${itemId}`} className="block font-medium">Why</label>
      <select id={`cat-${itemId}`} name="category" required className="field mt-1">
        {categories.map((category) => (
          <option key={category} value={category}>
            {CATEGORY_WORDS[category] ?? category}
          </option>
        ))}
      </select>
      <label htmlFor={`reason-${itemId}`} className="mt-3 block font-medium">
        In your own words
      </label>
      <textarea
        id={`reason-${itemId}`}
        name="reason"
        required
        minLength={20}
        maxLength={1000}
        rows={4}
        className="field mt-1"
      />
      <p className="mt-1 text-sm text-[var(--muted)]">
        This is published with the results, attributed to &ldquo;Juror n of
        m&rdquo;. Your name is not shown.
      </p>
      <div className="mt-2 flex gap-2">
        <button type="submit" className="btn btn-primary">Hold it back</button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}
