"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Empty, Loading, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Entry = {
  id: number;
  administrator: string;
  action: string;
  subject_type: string;
  subject_id: number | null;
  old_value: unknown;
  new_value: unknown;
  reason: string | null;
  at: string;
};

type Payload = { explanation: string; items: Entry[] };

const WORDS: Record<string, string> = {
  change_setting: "changed a rule",
  prepare_ballot: "prepared a ballot",
  redraw_jury: "drew a new jury",
  open_ballot: "opened a ballot",
  close_ballot: "closed a ballot",
  publish_summary: "published a results document",
  recommend_references: "asked AI to suggest references",
  force_relabel: "asked the platform to file a post again",
  grant_admin: "was made an administrator",
  revoke_admin: "stopped being an administrator",
};

export default function AdminLogPage() {
  useDocumentTitle("Everything an administrator has done");
  const [data, setData] = useState<Payload | null>(null);

  useEffect(() => {
    void get<Payload>("/admin/log?limit=50").then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <Loading what="the administrator log" />;

  return (
    <>
      <PageHeader title="Everything an administrator has done" lead={data.explanation} />
      <div className="mx-auto max-w-4xl px-4 py-8">
        {data.items.length === 0 ? (
          <Empty>No administrator has done anything yet.</Empty>
        ) : (
          <ol className="space-y-3">
            {data.items.map((entry) => (
              <li key={entry.id} className="card p-4">
                <p>
                  <strong>{entry.administrator}</strong>{" "}
                  {WORDS[entry.action] ?? entry.action}
                  {entry.subject_id ? ` (${entry.subject_type} #${entry.subject_id})` : ""}
                </p>
                <p className="text-xs text-[var(--muted)]">
                  {new Date(entry.at).toLocaleString()}
                </p>
                {entry.reason ? (
                  <p className="mt-1 text-sm">Reason given: {entry.reason}</p>
                ) : null}
                {entry.old_value || entry.new_value ? (
                  <details className="mt-1 text-sm">
                    <summary className="cursor-pointer">What changed</summary>
                    <pre className="mt-1 overflow-x-auto rounded bg-[var(--accent-soft)] p-2 text-xs">
                      {JSON.stringify({ before: entry.old_value, after: entry.new_value }, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </div>
    </>
  );
}
