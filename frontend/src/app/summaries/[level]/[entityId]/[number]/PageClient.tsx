"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { apiBase, get } from "@/lib/api";
import { Badge, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type ResultRow = {
  position: number;
  umbrella: string;
  solution_text: string;
  solution_version: number;
  solution_version_hash: string;
  author_display_at_snapshot: string;
  ai_influence_label: string;
  yes: number;
  no: number;
  result: string;
};

type HeldBack = {
  position: number;
  umbrella: string;
  solution_text: string;
  solution_version: number;
  jury_reasons: { juror: string; category: string; reason: string }[];
};

type Payload = {
  summary_hash: string;
  published_at: string;
  mailto: string;
  document: {
    header: Record<string, string | number | null>;
    results: ResultRow[];
    held_back: HeldBack[];
    how_this_was_produced: {
      heading: string;
      text: string;
      settings_in_force: string;
      rule_version: string;
    }[];
    empty_note: string | null;
    send_to_representatives: {
      recipients: { office: string; email: string }[];
      note: string;
      demo_note: string;
    };
  };
  verify: { hash: string; algorithm: string; explanation: string; hash_list_url: string };
};

export default function SummaryPage() {
  useDocumentTitle("Ballot results");
  const { level, entityId, number } = useParams<{
    level: string;
    entityId: string;
    number: string;
  }>();
  const base = `/summaries/${level}/${entityId}/${number}`;
  const [data, setData] = useState<Payload | null>(null);
  const [check, setCheck] = useState<string | null>(null);

  useEffect(() => {
    void get<Payload>(base).then(setData).catch(() => setData(null));
  }, [base]);

  let body: ReactNode;
  if (!data) {
    body = <Loading what="this document" />;
  } else {
    const header = data.document.header;
    body = (
      <>
        <Section title="Who voted">
          <ul className="space-y-1 text-sm">
            <li>Ballot opened: {String(header.ballot_opened_at ?? "—")}</li>
            <li>Ballot closed: {String(header.ballot_closed_at ?? "—")}</li>
            <li>Active residents at the snapshot: {String(header.active_users_at_snapshot)}</li>
            <li>Residents who voted: {String(header.members_who_voted)}</li>
            <li>{String(header.verification_mix)}</li>
            <li>Jury: {String(header.jury)}</li>
          </ul>
          <Notice>{String(header.residency_note)}</Notice>
        </Section>

        {data.document.empty_note ? (
          <Section title="Results">
            <Notice>{data.document.empty_note}</Notice>
          </Section>
        ) : (
          <Section title="Results" description="Every item that went to the vote, including the ones that failed.">
            <ol className="space-y-4">
              {data.document.results.map((row) => (
                <li key={row.position} className="card p-4">
                  <p className="text-sm font-medium">
                    {row.position}. {row.umbrella} ·{" "}
                    <Badge>{row.result}</Badge>
                  </p>
                  <p className="mt-1 whitespace-pre-line">{row.solution_text}</p>
                  <p className="mt-2 font-bold">
                    {row.yes} yes · {row.no} no
                  </p>
                  <p className="mt-1 break-all text-xs text-[var(--muted)]">
                    Version {row.solution_version} · fingerprint {row.solution_version_hash}
                    <br />
                    Proposed by {row.author_display_at_snapshot} · {row.ai_influence_label}
                  </p>
                </li>
              ))}
            </ol>
          </Section>
        )}

        {data.document.held_back.length ? (
          <Section
            title="Held back by the jury"
            description="These did not go to the vote. Every seated juror's reason is published in full."
          >
            <ol className="space-y-4">
              {data.document.held_back.map((row) => (
                <li key={row.position} className="card p-4">
                  <p className="text-sm font-medium">{row.umbrella}</p>
                  <p className="mt-1 whitespace-pre-line">{row.solution_text}</p>
                  <ul className="mt-2 space-y-2 text-sm">
                    {row.jury_reasons.map((reason, index) => (
                      <li key={index} className="rounded-lg border border-[var(--line)] p-2">
                        <span className="font-medium">{reason.juror}</span> —{" "}
                        {reason.category.replace(/_/g, " ")}
                        <p className="mt-1">{reason.reason}</p>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </Section>
        ) : null}

        <Section title="How this was produced" description="In plain English, with the exact numbers that were in force.">
          <ol className="space-y-3">
            {data.document.how_this_was_produced.map((section) => (
              <li key={section.heading} className="card p-3">
                <h3 className="font-bold">{section.heading}</h3>
                <p className="mt-1 text-sm">{section.text}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Settings in force: {section.settings_in_force} ({section.rule_version})
                </p>
              </li>
            ))}
          </ol>
        </Section>

        <Section title="Verify this document">
          <p className="break-all font-mono text-sm">{data.summary_hash}</p>
          <p className="mt-2 text-sm">{data.verify.explanation}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <a className="btn no-underline" href={`${apiBase()}${base}/json`}>
              Download the JSON
            </a>
            <a className="btn no-underline" href={`${apiBase()}${base}/pdf`}>
              Download the PDF
            </a>
            <Link className="btn no-underline" href="/summaries/hashes">
              Every published fingerprint
            </Link>
            <button
              type="button"
              className="btn"
              onClick={async () => {
                const body = await get<{ match: boolean; verdict: string }>(`${base}/verify`);
                setCheck(body.verdict);
              }}
            >
              Check it now
            </button>
          </div>
          {check ? <div className="mt-2"><Notice kind="good">{check}</Notice></div> : null}
        </Section>

        <Section title="Send this to your representatives">
          <p className="text-sm">{data.document.send_to_representatives.note}</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {data.document.send_to_representatives.demo_note}
          </p>
          <ul className="mt-2 text-sm">
            {data.document.send_to_representatives.recipients.map((recipient) => (
              <li key={recipient.office}>
                {recipient.office} — {recipient.email}
              </li>
            ))}
          </ul>
          <a className="btn btn-primary mt-3 no-underline" href={data.mailto}>
            Send to my representatives
          </a>
        </Section>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={data ? `Ballot results — ${data.document.header.community_label}` : "Ballot results"}
        lead={data ? `Cycle ${data.document.header.cycle_number}` : undefined}
      />
      <div className="mx-auto max-w-3xl px-4 py-8">{body}</div>
    </>
  );
}
