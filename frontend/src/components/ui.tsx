"use client";

/** Small pieces every page uses. Plain language, accessible by default. */

import Link from "next/link";
import { ReactNode } from "react";

export function PageHeader({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12">
        <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
        {lead ? <p className="mt-2 max-w-2xl text-sm sm:text-base">{lead}</p> : null}
        {children}
      </div>
    </header>
  );
}

export function Section({
  title,
  description,
  children,
  id,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="mt-8">
      <h2 className="text-xl font-bold">{title}</h2>
      {description ? (
        <p className="mt-1 text-sm text-[var(--muted)]">{description}</p>
      ) : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function Notice({
  kind = "info",
  children,
  alertRef,
}: {
  kind?: "info" | "good" | "bad";
  children: ReactNode;
  /** A bad Notice can receive focus (WCAG 2.1 AA — focus moves to the error
   * on a failed submit, `useFormError`'s `fail()` uses this when no single
   * field is to blame). `tabIndex={-1}` keeps it out of normal tab order. */
  alertRef?: React.RefObject<HTMLParagraphElement | null>;
}) {
  const colour =
    kind === "bad"
      ? "border-[var(--bad)] text-[var(--bad)]"
      : kind === "good"
        ? "border-[var(--good)] text-[var(--good)]"
        : "border-[var(--line)] text-[var(--muted)]";
  return (
    <p
      ref={kind === "bad" ? alertRef : undefined}
      tabIndex={kind === "bad" ? -1 : undefined}
      role={kind === "bad" ? "alert" : "status"}
      className={`rounded-lg border-l-4 bg-[var(--surface)] px-3 py-2 text-sm ${colour}`}
    >
      {children}
    </p>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}

export function Explainer({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="mt-2 text-sm text-[var(--muted)]">
      <summary className="cursor-pointer font-medium text-[var(--foreground)]">
        {title}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-[var(--line)] px-3 py-6 text-center text-sm text-[var(--muted)]">
      {children}
    </p>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p role="status" className="py-6 text-sm text-[var(--muted)]">
      Loading {what}…
    </p>
  );
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="text-sm font-medium">
      ← {children}
    </Link>
  );
}

export function AiInfluence({
  influence,
}: {
  influence?: { label: string; explanation: string };
}) {
  if (!influence) return null;
  return (
    <Explainer title={influence.label}>
      <p>{influence.explanation}</p>
    </Explainer>
  );
}

export function Markdown({ text }: { text: string }) {
  /* The legal pages are the only markdown the platform renders, and they are
     written by the platform itself, not by users. Headings, lists, tables,
     quotes, bold and code are enough for them. */
  const html = renderMarkdown(text);
  return (
    <div className="prose-plain" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(text: string): string {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      (_m, label, href) => `<a href="${escapeHtml(href)}">${label}</a>`,
    );
}

function renderMarkdown(source: string): string {
  const out: string[] = [];
  const lines = source.split("\n");
  let listType: "ul" | "ol" | null = null;
  let inTable = false;
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${inline(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };
  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`);
      listType = null;
    }
  };
  const closeTable = () => {
    if (inTable) {
      out.push("</tbody></table>");
      inTable = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      closeList();
      closeTable();
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      closeList();
      closeTable();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    if (trimmed.startsWith("> ")) {
      flushParagraph();
      closeList();
      closeTable();
      out.push(`<blockquote>${inline(trimmed.slice(2))}</blockquote>`);
      continue;
    }
    if (/^\|(.+)\|$/.test(trimmed)) {
      flushParagraph();
      closeList();
      const cells = trimmed.slice(1, -1).split("|").map((c) => c.trim());
      if (cells.every((c) => /^-{2,}$/.test(c.replace(/:/g, "")))) continue;
      if (!inTable) {
        inTable = true;
        out.push(
          `<table><thead><tr>${cells
            .map((c) => `<th>${inline(c)}</th>`)
            .join("")}</tr></thead><tbody>`,
        );
      } else {
        out.push(`<tr>${cells.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`);
      }
      continue;
    }
    closeTable();
    const bullet = /^[-*]\s+(.*)$/.exec(trimmed);
    const numbered = /^\d+\.\s+(.*)$/.exec(trimmed);
    if (bullet || numbered) {
      flushParagraph();
      const wanted = bullet ? "ul" : "ol";
      if (listType !== wanted) {
        closeList();
        out.push(`<${wanted}>`);
        listType = wanted;
      }
      out.push(`<li>${inline((bullet ?? numbered)![1])}</li>`);
      continue;
    }
    closeList();
    paragraph.push(trimmed);
  }
  flushParagraph();
  closeList();
  closeTable();
  return out.join("\n");
}
