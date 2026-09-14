"use client";

import { useEffect } from "react";

/**
 * Give each page its own name in the browser tab.
 *
 * WCAG 2.4.2 and CLAUDE.md §8: a person with twenty tabs open, and a person
 * listening to a screen reader announce the page, both need to know which page
 * they are on. Every page is a client component here, so the title is set from
 * the page rather than from route metadata, and it updates on navigation
 * between pages too.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Direct Democracy Cali`;
  }, [title]);
}
