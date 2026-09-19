import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/Session";
import SiteNav from "@/components/SiteNav";

export const metadata: Metadata = {
  title: {
    default: "Direct Democracy Cali",
    // Every route sets its own `metadata.title`, rendered into this
    // template server-side, so the title in the served HTML is right
    // before any client JavaScript runs (WCAG 2.4.2; CLAUDE.md §8; audit
    // demo-01 run 2 — every route used to serve the same title and set the
    // real one from a client-side useEffect after hydration).
    template: "%s · Direct Democracy Cali",
  },
  description:
    "Document a problem in your community, work on solutions with your neighbours, vote, and send the result to the people who represent you.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to the main content
        </a>
        <SessionProvider>
          <SiteNav />
          <main id="main">{children}</main>
          <footer className="mt-16 border-t border-[var(--line)] bg-[var(--surface)]">
            <div className="mx-auto max-w-4xl px-4 py-8 text-sm text-[var(--muted)]">
              <p className="font-medium text-[var(--foreground)]">
                Everything this platform does is published.
              </p>
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                <li><a href="/settings">Every rule and its value</a></li>
                <li><a href="/ai/actions">Every action AI has taken</a></li>
                <li><a href="/admin/log">Every action an administrator has taken</a></li>
                <li><a href="/legal/privacy">Privacy</a></li>
                <li><a href="/legal/terms">Terms</a></li>
                <li><a href="/legal/cookies">Cookies</a></li>
              </ul>
              <p className="mt-4">
                A demo build. The legal pages are drafts, the officials directory
                holds test addresses, and residency is self-declared.
              </p>
            </div>
          </footer>
        </SessionProvider>
      </body>
    </html>
  );
}
