"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Empty, Loading, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Row = {
  community: { level: string; entity_id: number; label: string };
  cycle_number: number;
  published_at: string;
  summary_hash: string;
  url: string;
};

export default function HashesPage() {
  useDocumentTitle("Every published fingerprint");
  const [data, setData] = useState<{ explanation: string; summaries: Row[] } | null>(null);

  useEffect(() => {
    void get<{ explanation: string; summaries: Row[] }>("/summaries/hashes")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  return (
    <>
      <PageHeader title="Every published document, and its fingerprint" lead={data?.explanation} />
      <div className="mx-auto max-w-4xl px-4 py-8">
        {!data ? (
          <Loading what="the fingerprints" />
        ) : data.summaries.length === 0 ? (
          <Empty>Nothing has been published yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Published results documents and their fingerprints</caption>
              <thead>
                <tr className="border-b border-[var(--line)] text-left">
                  <th scope="col" className="py-2 pr-3">Community</th>
                  <th scope="col" className="py-2 pr-3">Cycle</th>
                  <th scope="col" className="py-2 pr-3">Published</th>
                  <th scope="col" className="py-2">Fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {data.summaries.map((row) => (
                  <tr key={row.url} className="border-b border-[var(--line)]">
                    <td className="py-2 pr-3">{row.community.label}</td>
                    <td className="py-2 pr-3">
                      <Link href={row.url}>{row.cycle_number}</Link>
                    </td>
                    <td className="py-2 pr-3">{new Date(row.published_at).toLocaleString()}</td>
                    <td className="break-all py-2 font-mono text-xs">{row.summary_hash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
