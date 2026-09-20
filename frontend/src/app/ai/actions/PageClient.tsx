"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Empty, Loading, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Action = {
  id: number;
  action_type: string;
  subject_type: string;
  subject_id: number;
  model: string;
  prompt_file: string;
  prompt_hash: string;
  input_hash: string;
  output: Record<string, unknown>;
  confidence: number | null;
  human_outcome: string;
  created_at: string;
};

type Payload = { explanation: string; items: Action[]; next_cursor: number | null };

const OUTCOMES: Record<string, string> = {
  unreviewed: "Nobody has reviewed this yet",
  confirmed: "A person confirmed it",
  corrected: "A person corrected it",
  accepted: "A person found it useful",
  rejected: "People rejected it",
};

export default function AiActionsPage() {
  useDocumentTitle("Everything AI has done here");
  const [data, setData] = useState<Payload | null>(null);

  useEffect(() => {
    void get<Payload>("/ai/actions?limit=50").then(setData).catch(() => setData(null));
  }, []);

  return (
    <>
      <PageHeader title="Everything AI has done here" lead={data?.explanation} />
      <div className="mx-auto max-w-4xl px-4 py-8">
        {!data ? (
          <Loading what="the AI log" />
        ) : data.items.length === 0 ? (
          <Empty>No AI has acted on this platform yet.</Empty>
        ) : (
          <ol className="space-y-3">
            {data.items.map((action) => (
              <li key={action.id} className="card p-4">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="badge">{action.action_type}</span>
                  <span className="text-sm">
                    on {action.subject_type === "label_preview" ? "a draft" : action.subject_type}
                    {" "}#{action.subject_id}
                  </span>
                  <span className="ml-auto text-xs text-[var(--muted)]">
                    {new Date(action.created_at).toLocaleString()}
                  </span>
                </div>
                <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
                  <div><dt className="inline font-medium">Model: </dt><dd className="inline">{action.model}</dd></div>
                  <div><dt className="inline font-medium">Prompt file: </dt><dd className="inline">{action.prompt_file}</dd></div>
                  <div>
                    <dt className="inline font-medium">Confidence: </dt>
                    <dd className="inline">{action.confidence ?? "not given"}</dd>
                  </div>
                  <div>
                    <dt className="inline font-medium">What happened next: </dt>
                    <dd className="inline">
                      {action.subject_type === "label_preview" && action.human_outcome === "unreviewed"
                        ? "Suggestion on a draft — not posted"
                        : OUTCOMES[action.human_outcome] ?? action.human_outcome}
                    </dd>
                  </div>
                </dl>
                <details className="mt-2 text-sm">
                  <summary className="cursor-pointer font-medium">
                    Exactly what it answered, and the fingerprints of what it was given
                  </summary>
                  <p className="mt-2 break-all text-xs text-[var(--muted)]">
                    Prompt file fingerprint: {action.prompt_hash}
                    <br />
                    Input fingerprint: {action.input_hash}
                  </p>
                  <pre className="mt-2 overflow-x-auto rounded bg-[var(--accent-soft)] p-2 text-xs">
                    {JSON.stringify(action.output, null, 2)}
                  </pre>
                </details>
              </li>
            ))}
          </ol>
        )}
      </div>
    </>
  );
}
