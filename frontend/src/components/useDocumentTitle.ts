"use client";

import { useEffect } from "react";

/**
 * Give each page its own name in the browser tab.
 *
 * WCAG 2.4.2 and CLAUDE.md §8: a person with twenty tabs open, and a person
 * listening to a screen reader announce the page, both need to know which
 * page they are on. Each route's `page.tsx` now exports server-side
 * `metadata` too, so the title in the served HTML is already correct before
 * any client JavaScript runs (audit demo-01 run 2); this hook is kept
 * alongside it so a client-side navigation between routes updates the tab
 * title the same way.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Direct Democracy CA`;
  }, [title]);
}
