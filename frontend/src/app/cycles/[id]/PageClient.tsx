"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Badge, BackLink, Loading, PageHeader, Section } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Cycle = {
  id: number;
  number: number;
  state: string;
  community: { level: string; entity_id: number; label: string };
  active_users_at_prepare: number | null;
  settings_in_force: Record<string, unknown>;
  item_count: number;
  jury: { drawn: number; seated: number | null; size_requested: number; eligible_pool_size: number } | null;
  would_close_on: string | null;
  transitions: { state: string; at: string; by: number | string }[];
};

export default function CyclePage() {
  useDocumentTitle("A ballot cycle");
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Cycle | null>(null);

  useEffect(() => {
    void get<Cycle>(`/cycles/${id}`).then(setData).catch(() => setData(null));
  }, [id]);

  return (
    <>
      <PageHeader
        title={data ? `${data.community.label} — cycle ${data.number}` : "A ballot cycle"}
        lead={data ? `This cycle is ${data.state.replace("_", " ")}.` : undefined}
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        {!data ? (
          <Loading what="this cycle" />
        ) : (
          <>
        <BackLink href="/ballot">Back to the ballot</BackLink>

        <Section title="Where it stands">
          <ul className="space-y-1 text-sm">
            <li>Items on the ballot: {data.item_count}</li>
            <li>Active residents when it was prepared: {data.active_users_at_prepare ?? "—"}</li>
            {data.jury ? (
              <li>
                Jury: {data.jury.drawn} drawn of {data.jury.size_requested} asked for,{" "}
                {data.jury.seated ?? "not yet seated"} seated, drawn from a pool of{" "}
                {data.jury.eligible_pool_size}
              </li>
            ) : (
              <li>No jury was drawn.</li>
            )}
            {data.would_close_on ? (
              <li>
                The ballot window says it would close on{" "}
                {new Date(data.would_close_on).toLocaleString()}. In this build the
                director closes it by hand.
              </li>
            ) : null}
          </ul>
          <p className="mt-3">
            <Link href={`/ballot`}>See the items and vote</Link>
          </p>
        </Section>

        <Section title="What happened, and when">
          <ol className="space-y-1 text-sm">
            {data.transitions.map((transition, index) => (
              <li key={index}>
                <Badge>{transition.state.replace("_", " ")}</Badge>{" "}
                {new Date(transition.at).toLocaleString()}
              </li>
            ))}
          </ol>
        </Section>

        <Section
          title="The rules that were in force when this ballot was prepared"
          description="Recorded on the cycle, so the published document can print exactly the numbers that produced it."
        >
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Settings recorded on this cycle</caption>
              <thead>
                <tr className="border-b border-[var(--line)] text-left">
                  <th scope="col" className="py-1 pr-3">Rule</th>
                  <th scope="col" className="py-1">Value</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.settings_in_force)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([key, value]) => (
                    <tr key={key} className="border-b border-[var(--line)]">
                      <th scope="row" className="py-1 pr-3 text-left font-mono font-normal">{key}</th>
                      <td className="py-1">{String(value)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Section>
          </>
        )}
      </div>
    </>
  );
}
