"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { ApiError, get, put } from "@/lib/api";
import { useSession } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import { Badge, Empty, Explainer, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";
import { BallotExplainer, useSettingsMap, zeroItemBallotSentence } from "@/content/explainers";

type BallotItem = {
  ballot_item_id: number;
  position: number;
  umbrella: string | null;
  solution_id: number;
  frozen_version: number;
  frozen_text: string;
  frozen_hash: string | null;
  net_score_at_snapshot: number;
  held_back: boolean;
  votable: boolean;
  my_vote: string | null;
  yes_count: number | null;
  no_count: number | null;
  result: string | null;
};

type Ballot = {
  cycle_id: number;
  cycle_number: number;
  state: string;
  community: { label: string };
  you_can_vote: boolean;
  settings_in_force: Record<string, number | string>;
  ordering: { version: string; explanation: string };
  privacy_note: string;
  items: BallotItem[];
};

type CycleList = { cycles: { id: number; number: number; state: string }[] };

const STATE_WORDS: Record<string, string> = {
  workshop: "still in the workshop",
  prepared: "prepared",
  jury_review: "with the jury",
  open: "open for voting now",
  closed: "closed, results being published",
  published: "published",
};

export default function BallotPage() {
  useDocumentTitle("The ballot");
  const { me, loading } = useSession();
  const settings = useSettingsMap();
  const [error, setError] = useState<string | null>(null);
  const { data: ballots, reload } = useLoader<Ballot[]>(async () => {
    if (!me) return [];
    const found: Ballot[] = [];
    for (const community of me.home_communities) {
      try {
        const list = await get<CycleList>(
          `/communities/${community.level}/${community.entity_id}/cycles`,
        );
        const live = list.cycles.find((c) => c.state !== "published") ?? list.cycles[0];
        if (!live) continue;
        found.push(await get<Ballot>(`/cycles/${live.id}/ballot`));
      } catch {
        // A community with no cycle yet simply has nothing to show.
      }
    }
    return found;
  }, [me]);

  async function vote(cycleId: number, itemId: number, choice: "yes" | "no") {
    setError(null);
    try {
      await put(`/cycles/${cycleId}/ballot/${itemId}/vote`, { choice });
      reload();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    }
  }

  let body: ReactNode;
  if (loading) {
    body = <Loading what="your ballots" />;
  } else if (!me) {
    body = (
      <Notice>
        <Link href="/login">Sign in</Link> to see your community&apos;s ballot.
      </Notice>
    );
  } else if (!ballots) {
    body = <Loading what="your ballots" />;
  } else {
    const list = ballots;
    body = (
      <>
        {error ? <Notice kind="bad">{error}</Notice> : null}
        {list.length === 0 ? (
          <Empty>
            No ballot has been prepared in your communities yet. Work on
            solutions in the <Link href="/home">workshop</Link> and they will get
            there.
          </Empty>
        ) : (
          list.map((ballot) => (
            <Section
              key={ballot.cycle_id}
              title={`${ballot.community.label} — cycle ${ballot.cycle_number}`}
              description={`This ballot is ${STATE_WORDS[ballot.state] ?? ballot.state}. ${ballot.ordering.explanation}`}
            >
              <Notice>{ballot.privacy_note}</Notice>
              {ballot.items.length === 0 ? (
                <Empty>{zeroItemBallotSentence(ballot.settings_in_force)}</Empty>
              ) : (
                <ol className="mt-3 space-y-3">
                  {ballot.items.map((item) => (
                    <li key={item.ballot_item_id} className="card p-4">
                      <p className="text-sm font-medium">
                        {item.position}. {item.umbrella}
                        {item.held_back ? <> · <Badge>held back by the jury</Badge></> : null}
                        {item.result ? <> · <Badge>{item.result.replace("_", " ")}</Badge></> : null}
                      </p>
                      <p className="mt-1 whitespace-pre-line">{item.frozen_text}</p>
                      <p className="mt-1 break-all text-xs text-[var(--muted)]">
                        Version {item.frozen_version} · fingerprint {item.frozen_hash}
                      </p>
                      {item.yes_count !== null ? (
                        <p className="mt-2 text-sm font-bold">
                          {item.yes_count} yes · {item.no_count} no
                        </p>
                      ) : null}
                      {item.votable && ballot.you_can_vote ? (
                        <div className="mt-3 flex items-center gap-2">
                          {(["yes", "no"] as const).map((choice) => (
                            <button
                              key={choice}
                              type="button"
                              className={`btn ${item.my_vote === choice ? "btn-primary" : ""}`}
                              aria-pressed={item.my_vote === choice}
                              onClick={() => void vote(ballot.cycle_id, item.ballot_item_id, choice)}
                            >
                              {choice === "yes" ? "Yes" : "No"}
                            </button>
                          ))}
                          <span className="text-sm text-[var(--muted)]">
                            {item.my_vote
                              ? `You voted ${item.my_vote}. You can change it until the ballot closes.`
                              : "You have not voted on this yet."}
                          </span>
                        </div>
                      ) : item.held_back ? (
                        <p className="mt-2 text-sm text-[var(--muted)]">
                          The jury held this back, so the community is not voting on
                          it this cycle. Their written reasons are published with the
                          results.
                        </p>
                      ) : null}
                      <p className="mt-2 text-sm">
                        <Link href={`/solutions/${item.solution_id}`}>
                          See this solution in the workshop
                        </Link>
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </Section>
          ))
        )}
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="The ballot"
        lead={
          me && ballots
            ? "Solutions your community worked on, frozen as they were when the ballot was prepared. One vote each, counted the same."
            : undefined
        }
      />
      <div className={`mx-auto px-4 py-8 ${me && ballots ? "max-w-3xl" : "max-w-md"}`}>
        <Explainer title="How the ballot works">
          {settings ? (
            <BallotExplainer settings={settings} />
          ) : (
            <Loading what="the explanation" />
          )}
        </Explainer>
        <div className="mt-4">{body}</div>
      </div>
    </>
  );
}
