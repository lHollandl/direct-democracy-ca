"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { Loading, Markdown, Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Legal = {
  version: string;
  is_draft: boolean;
  draft_warning: string;
  markdown: string;
};

export default function LegalPage() {
  useDocumentTitle("Privacy policy");
  const [doc, setDoc] = useState<Legal | null>(null);

  useEffect(() => {
    void get<Legal>("/legal/privacy").then(setDoc).catch(() => setDoc(null));
  }, []);

  return (
    <>
      <PageHeader title="Privacy policy" lead={doc ? `Version ${doc.version}` : undefined} />
      <div className="mx-auto max-w-2xl px-4 py-8">
        {!doc ? (
          <Loading what="this page" />
        ) : (
          <>
            {doc.is_draft ? <Notice kind="bad">{doc.draft_warning}</Notice> : null}
            <div className="mt-6">
              <Markdown text={doc.markdown} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
