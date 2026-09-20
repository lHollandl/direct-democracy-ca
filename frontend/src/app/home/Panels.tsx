"use client";

/** The ballot and jury panels on Home (DEMOCRACY.md §12.2). */

import Link from "next/link";
import { useState } from "react";
import { ApiError, put } from "@/lib/api";
import { Notice } from "@/components/ui";

export type CycleEntry = {
  community: { level: string; entity_id: number; name: string; label: string };
  cycle: {
    id: number;
    number: number;
    state: string;
    opened_at: string | null;
    expected_close: string | null;
  } | null;
  last_closed_at: string | null;
  next_ballot_expected: string;
  last_jury_drawn_at: string | null;
  next_jury_draw_expected: string;
  my_jury_status: "none" | "drawn" | "accepted" | "declined" | "no_response";
  respond_by: string | null;
};

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString();
}

const JURY_STATUS_WORDS: Record<CycleEntry["my_jury_status"], string> = {
  none: "You have not been drawn for this cycle's jury.",
  drawn: "You have been drawn for this cycle's jury and have not answered yet.",
  accepted: "You accepted jury duty for this cycle.",
  declined: "You declined jury duty for this cycle.",
  no_response: "You were drawn but did not answer in time, so you were not seated.",
};

export function BallotPanel({ entries }: { entries: CycleEntry[] }) {
  return (
    <section className="card p-4">
      <h2 className="font-bold">Ballot</h2>
      <ul className="mt-2 space-y-2 text-sm">
        {entries.map((entry) => (
          <li key={`ballot-${entry.community.level}-${entry.community.entity_id}`}>
            <span className="font-medium">{entry.community.label}:</span>{" "}
            {entry.cycle && entry.cycle.state === "open" ? (
              <>Open — expected to close {formatDate(entry.cycle.expected_close)}</>
            ) : (
              <>
                Next ballot expected {formatDate(entry.next_ballot_expected)}
                {entry.last_closed_at ? (
                  <> · Last ballot closed {formatDate(entry.last_closed_at)}</>
                ) : null}
              </>
            )}
          </li>
        ))}
      </ul>
      <Link href="/ballot" className="btn mt-3 no-underline">
        Go to the ballot
      </Link>
    </section>
  );
}

export function JuryPanel({ entries }: { entries: CycleEntry[] }) {
  return (
    <section className="card p-4">
      <h2 className="font-bold">Jury</h2>
      <ul className="mt-2 space-y-2 text-sm">
        {entries.map((entry) => (
          <li key={`jury-${entry.community.level}-${entry.community.entity_id}`}>
            <span className="font-medium">{entry.community.label}:</span>{" "}
            {entry.last_jury_drawn_at ? (
              <>Last jury drawn {formatDate(entry.last_jury_drawn_at)}</>
            ) : (
              <>No jury has been drawn yet</>
            )}
            {" · "}Next draw expected {formatDate(entry.next_jury_draw_expected)}
            <br />
            <span className="text-[var(--muted)]">
              {JURY_STATUS_WORDS[entry.my_jury_status]}
              {entry.my_jury_status === "drawn" && entry.respond_by
                ? ` Reply by ${formatDate(entry.respond_by)}.`
                : ""}
            </span>
          </li>
        ))}
      </ul>
      <Link href="/jury" className="btn mt-3 no-underline">
        Go to jury duty
      </Link>
    </section>
  );
}

type PinnedBallotItem = {
  ballot_item_id: number;
  position: number;
  umbrella: string | null;
  frozen_text: string;
  held_back: boolean;
  votable: boolean;
  my_vote: string | null;
  result: string | null;
};

export type PinnedBallot = {
  cycle_id: number;
  community_label: string;
  you_can_vote: boolean;
  items: PinnedBallotItem[];
};

export function PinnedBallotBlock({
  ballots,
  onVoted,
}: {
  ballots: PinnedBallot[];
  onVoted: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function vote(cycleId: number, itemId: number, choice: "yes" | "no") {
    setError(null);
    try {
      await put(`/cycles/${cycleId}/ballot/${itemId}/vote`, { choice });
      onVoted();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    }
  }

  const anyItems = ballots.some((b) => b.items.length > 0);
  if (!anyItems) return null;

  return (
    <section className="mb-6">
      <h2 className="text-lg font-bold">On your ballot now</h2>
      {error ? <Notice kind="bad">{error}</Notice> : null}
      {ballots.map((ballot) =>
        ballot.items.length === 0 ? null : (
          <div key={ballot.cycle_id} className="mt-2">
            <p className="text-sm font-medium text-[var(--muted)]">{ballot.community_label}</p>
            <ol className="mt-2 space-y-2">
              {ballot.items.map((item) => (
                <li key={item.ballot_item_id} className="card p-3">
                  <p className="text-sm font-medium">
                    {item.position}. {item.umbrella}
                  </p>
                  <p className="mt-1 whitespace-pre-line text-sm">{item.frozen_text}</p>
                  {item.votable && ballot.you_can_vote ? (
                    <div className="mt-2 flex items-center gap-2">
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
                    </div>
                  ) : item.held_back ? (
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      The jury held this back this cycle.
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        ),
      )}
    </section>
  );
}
