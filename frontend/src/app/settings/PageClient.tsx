"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Loading, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Setting = {
  key: string;
  value: unknown;
  meaning: string;
  defined_in: string;
  effective_from: string | null;
  reason: string | null;
  set_by: string;
};

type Payload = { explanation: string; rules_version: string; settings: Setting[] };

export default function SettingsPage() {
  useDocumentTitle("Every rule and its value");
  const [data, setData] = useState<Payload | null>(null);

  useEffect(() => {
    void get<Payload>("/settings").then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <Loading what="the rules" />;

  return (
    <>
      <PageHeader
        title="Every rule, and the number it is set to"
        lead={data.explanation}
      />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <p className="text-sm text-[var(--muted)]">
          Ranking and threshold rules version: <strong>{data.rules_version}</strong>
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Every platform setting, its current value, what it means and when
              it last changed
            </caption>
            <thead>
              <tr className="border-b border-[var(--line)] text-left">
                <th scope="col" className="py-2 pr-3">Rule</th>
                <th scope="col" className="py-2 pr-3">Value</th>
                <th scope="col" className="py-2 pr-3">What it means</th>
                <th scope="col" className="py-2">In force since</th>
              </tr>
            </thead>
            <tbody>
              {data.settings.map((row) => (
                <tr key={row.key} className="border-b border-[var(--line)] align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-mono font-normal">
                    {row.key}
                  </th>
                  <td className="py-2 pr-3 font-bold">{String(row.value)}</td>
                  <td className="py-2 pr-3">
                    {row.meaning}
                    <span className="block text-xs text-[var(--muted)]">
                      Written in {row.defined_in}
                    </span>
                    {row.reason ? (
                      <span className="block text-xs text-[var(--muted)]">
                        Last changed because: {row.reason}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2">
                    {row.effective_from
                      ? new Date(row.effective_from).toLocaleString()
                      : "—"}
                    <span className="block text-xs text-[var(--muted)]">
                      Set by {row.set_by}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
