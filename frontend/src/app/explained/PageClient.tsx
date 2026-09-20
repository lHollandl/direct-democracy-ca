"use client";

import Link from "next/link";
import { Explainer, Loading, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";
import {
  BallotExplainer,
  CycleRuleWords,
  JuryExplainer,
  useSettingsMap,
} from "@/content/explainers";
import { AMonthDiagram, PATH_STEPS, PathOfAProblemDiagram, aMonthSteps } from "./Diagrams";

export default function ExplainedPage() {
  useDocumentTitle("Direct Democracy Explained");
  const settings = useSettingsMap();
  const jurySize = settings ? settings.jury_size : null;

  return (
    <>
      <PageHeader
        title="Direct Democracy Explained"
        lead="How the platform actually works, from a problem in your neighborhood to a document your representatives can be held to."
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Section title="The short version">
          <ol className="grid gap-4 sm:grid-cols-2">
            <li className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">Step 1</p>
              <h3 className="mt-1 font-bold">Say what is wrong, and what to do</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Nothing can be posted here without at least one proposed
                solution. This is not a place to complain.
              </p>
            </li>
            <li className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">Step 2</p>
              <h3 className="mt-1 font-bold">Work on it together</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Solutions that enough neighbors support become open to
                amendment. Anyone can propose a better wording; enough support
                and it becomes the text.
              </p>
            </li>
            <li className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">Step 3</p>
              <h3 className="mt-1 font-bold">
                {jurySize !== null
                  ? `${jurySize} neighbors check it over`
                  : "Neighbors check it over"}
              </h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {jurySize !== null
                  ? `Before a ballot, ${jurySize} residents drawn at random look at what qualified. They cannot change anything. They can hold something back, in public, with a reason.`
                  : "Before a ballot, residents drawn at random — see the settings page for how many — look at what qualified. They cannot change anything. They can hold something back, in public, with a reason."}
              </p>
            </li>
            <li className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">Step 4</p>
              <h3 className="mt-1 font-bold">
                The community votes, and the result is published
              </h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                One vote each, counted the same. The result is a public page
                with a fingerprint anyone can check, and one button that
                emails it to your representatives from your own address.
              </p>
            </li>
          </ol>
        </Section>

        <Section
          title="The path of a problem"
          description="DEMOCRACY.md §1 — how a post becomes pressure on the people who represent you."
        >
          <PathOfAProblemDiagram />
          <ol className="mt-4 list-decimal space-y-2 pl-6 text-sm">
            {PATH_STEPS.map((step) => (
              <li key={step.label}>{step.text}</li>
            ))}
            <li>
              The cycle continues: representatives hear the pressure, and the
              community keeps working in the same umbrella&apos;s workshop.
            </li>
          </ol>
        </Section>

        <Section title="Two clocks" description="DEMOCRACY.md §10.1 — the rhythm.">
          <p className="text-sm">
            The workshop never closes. The ballot is expected to open on{" "}
            {settings ? (
              <CycleRuleWords settings={settings} />
            ) : (
              "a schedule"
            )}
            . During this demo, every transition is still a director
            control, so these are always shown as{" "}
            <strong>expected</strong> dates, not guarantees.
          </p>
          {settings ? (
            <>
              <div className="mt-4">
                <AMonthDiagram settings={settings} />
              </div>
              <ol className="mt-4 list-decimal space-y-2 pl-6 text-sm">
                {aMonthSteps(settings).map((step) => (
                  <li key={step.label}>{step.text}</li>
                ))}
              </ol>
            </>
          ) : (
            <Loading what="the month diagram" />
          )}
        </Section>

        <Section title="Where AI is, and is not" description="CLAUDE.md §5.">
          <p className="text-sm">
            AI sorts posts into topics and suggests reference sources.
            It never decides anything: it never
            creates an umbrella, never casts or weights a vote, never
            advances a solution through any threshold, and never takes an
            action that changes the democratic weight of anything. Every AI
            action is labeled where it appears and recorded, permanently, in
            a{" "}
            <Link href="/ai/actions">public log</Link> — what acted, on what,
            when, and with what result. Every post and solution shows the
            share of its own text that AI wrote; on this build, that is
            always 0%, because this build offers no AI writing help.
          </p>
        </Section>

        <Section title="What is public">
          <ul className="mt-1 space-y-2 text-sm">
            <li>
              <Link href="/settings">Settings</Link> — every number that
              decides a democratic outcome, and what it means.
            </li>
            <li>
              <Link href="/ai/actions">AI actions</Link> — every action AI has
              ever taken on this platform.
            </li>
            <li>
              <Link href="/admin/log">Administrator log</Link> — every action
              an administrator has ever taken.
            </li>
            <li>
              <Link href="/results">Results</Link> — every published ballot
              result for your communities.
            </li>
            <li>
              <Link href="/summaries/hashes">Summary fingerprints</Link> — the
              cryptographic proof behind every published result, so nobody
              can quietly change one afterward.
            </li>
          </ul>
        </Section>

        <Section title="How the ballot and jury work">
          <Explainer title="How the ballot works">
            {settings ? (
              <BallotExplainer settings={settings} />
            ) : (
              <Loading what="the explanation" />
            )}
          </Explainer>
          <Explainer title="How the jury works">
            {settings ? (
              <JuryExplainer settings={settings} />
            ) : (
              <Loading what="the explanation" />
            )}
          </Explainer>
        </Section>
      </div>
    </>
  );
}
