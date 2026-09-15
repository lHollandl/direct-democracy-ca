"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Empty, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Summary = {
  cycle_number: number;
  published_at: string;
  summary_hash: string;
  url: string;
  item_count: number;
};

type Payload = {
  communities: {
    community: { level: string; entity_id: number; label: string };
    most_recent: Summary | null;
    past_cycles: Summary[];
    current_cycle_state: string | null;
  }[];
  note: string;
};

export default function ResultsPage() {
  useDocumentTitle("Results");
  const { me, loading } = useSession();
  const [data, setData] = useState<Payload | null>(null);

  useEffect(() => {
    if (!me) return;
    void get<Payload>("/results").then(setData).catch(() => setData(null));
  }, [me]);

  if (loading) return <Loading what="your results" />;
  if (!me) {
    return (
      <>
        <PageHeader title="Results" />
        <div className="mx-auto max-w-md px-4 py-8">
          <Notice>
            <Link href="/login">Sign in</Link> to see your communities&apos; results.
          </Notice>
        </div>
      </>
    );
  }
  if (!data) return <Loading what="your results" />;

  return (
    <>
      <PageHeader
        title="Results"
        lead="What your three communities have voted on. Everyone who reads one of these documents reads exactly the same thing."
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Notice>{data.note}</Notice>
        {data.communities.map((entry) => (
          <Section
            key={`${entry.community.level}:${entry.community.entity_id}`}
            title={entry.community.label}
            description={
              entry.current_cycle_state
                ? `The current cycle is ${entry.current_cycle_state.replace("_", " ")}.`
                : "No ballot cycle has started here yet."
            }
          >
            {entry.most_recent ? (
              <>
                <p>
                  <Link
                    href={`/summaries/${entry.community.level}/${entry.community.entity_id}/${entry.most_recent.cycle_number}`}
                    className="font-medium"
                  >
                    Cycle {entry.most_recent.cycle_number}
                  </Link>{" "}
                  · published{" "}
                  {new Date(entry.most_recent.published_at).toLocaleDateString()} ·{" "}
                  {entry.most_recent.item_count}{" "}
                  {entry.most_recent.item_count === 1 ? "item" : "items"}
                </p>
                <p className="break-all text-xs text-[var(--muted)]">
                  Fingerprint: {entry.most_recent.summary_hash}
                </p>
                {entry.past_cycles.length ? (
                  <ul className="mt-2 list-disc pl-5 text-sm">
                    {entry.past_cycles.map((summary) => (
                      <li key={summary.cycle_number}>
                        <Link
                          href={`/summaries/${entry.community.level}/${entry.community.entity_id}/${summary.cycle_number}`}
                        >
                          Cycle {summary.cycle_number}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <Empty>Nothing has been published here yet.</Empty>
            )}
          </Section>
        ))}
      </div>
    </>
  );
}
