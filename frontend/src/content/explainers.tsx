"use client";

/**
 * "How the ballot works" and "How the jury works" (DEMOCRACY.md §7, §8, §10;
 * ARCHITECTURE.md §9). Shared by `/ballot`, `/jury`, and `/explained`
 * (C1-06), so the explanation is written once. Every number is read from the
 * public settings at display time, through `useSettingsMap` below — never
 * typed into this text (CLAUDE.md Law 8).
 */

import Link from "next/link";
import { get } from "@/lib/api";
import { useLoader } from "@/components/useLoader";

export type SettingsMap = Record<string, number | string>;

export function useSettingsMap(): SettingsMap | null {
  const { data } = useLoader<SettingsMap>(async () => {
    const body = await get<{ settings: { key: string; value: number | string }[] }>(
      "/settings",
    );
    return Object.fromEntries(body.settings.map((s) => [s.key, s.value]));
  }, []);
  return data;
}

function thresholdSentence(pct: number | string, min: number | string): string {
  return `${pct}% of active users, or ${min} people — whichever is lower`;
}

function plural(n: number | string, word: string): string {
  return `${n} ${word}${Number(n) === 1 ? "" : "s"}`;
}

export function BallotExplainer({ settings }: { settings: SettingsMap }) {
  return (
    <div className="space-y-3">
      <p>
        A solution reaches the ballot by qualifying, not by anyone choosing
        it. It must be <strong>dominant</strong> — its net votes reach{" "}
        {thresholdSentence(settings.dominant_pct, settings.dominant_min)} —
        and it must have stayed dominant for at least{" "}
        {plural(settings.ballot_min_dominant_days, "day")}, with net votes at
        or above {thresholdSentence(settings.ballot_pct, settings.ballot_min)}.
      </p>
      <p>
        Once the director prepares the ballot, every qualifying solution&apos;s
        text is <strong>frozen</strong> exactly as it stood — nothing on the
        ballot can change afterward. A jury of residents (see &ldquo;How the
        jury works&rdquo;) may hold an item back, in public and with a
        reason, before the community votes on the rest.
      </p>
      <p>
        Every member gets one yes/no vote per item, and can change it any
        time until the ballot closes. An item passes when more members voted
        yes than no, and at least{" "}
        {plural(settings.ballot_quorum_min, "vote")}{" "}
        {Number(settings.ballot_quorum_min) === 1 ? "was" : "were"} cast on it
        in total — a tie fails.
      </p>
      <p>
        The result is published as one public document with a fingerprint
        anyone can check (see{" "}
        <Link href="/summaries/hashes">summary fingerprints</Link>).
      </p>
      <p>
        A ballot is expected to open on the first Sunday of each month and
        stay open {plural(settings.ballot_window_days, "day")}. During the
        demo, ballots are opened and closed by the administrator, so dates
        are expectations, not guarantees.
      </p>
    </div>
  );
}

export function JuryExplainer({ settings }: { settings: SettingsMap }) {
  return (
    <div className="space-y-3">
      <p>
        Before the whole community is asked to vote, a small jury of ordinary
        residents checks that what qualified is actually worth everyone&apos;s
        time. Jurors cannot edit anything and cannot reject a solution
        outright — the only thing a juror can do is{" "}
        <strong>hold one back</strong>, in public, with a written reason
        anyone can read.
      </p>
      <p>
        Jurors are drawn from the community&apos;s active members, excluding
        anyone who authored a version of, or proposed an amendment on, what
        is on this ballot, and administrators.{" "}
        {Number(settings.jury_no_repeat_cycles) === 0
          ? "Nobody is currently excluded for having served on a recent jury."
          : `Anyone who served on a jury for this community within the last ${plural(settings.jury_no_repeat_cycles, "cycle")} is excluded too.`}
      </p>
      <p>
        The draw is at random: the platform records the eligible pool and
        the random bytes it used, so the exact draw can be replayed
        afterward by anyone with the log. {settings.jury_size} jurors are
        drawn.
      </p>
      <p>
        Each juror has {plural(settings.jury_review_days, "day")} to reply.
        Declining draws a replacement immediately; not answering at all
        means the seat goes unfilled — nobody is substituted for silence. A
        solution is held back only when more than half of the seated jurors
        held it back.
      </p>
      <p>
        Every hold-back reason is published. To protect jurors from pressure
        over their vote, they are identified publicly only as &ldquo;Juror 1
        of N&rdquo; — never by name.
      </p>
    </div>
  );
}
