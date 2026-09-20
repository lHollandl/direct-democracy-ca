import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const ITEMS = [
  {
    title: "Today's technology, working for democracy",
    body: "Writing to a representative used to mean one letter from one person. Here a whole community drafts a proposal, improves it, and votes on it together, and every step is on the public record.",
  },
  {
    title: "More power to the people",
    body: "Every vote counts the same. What your community passes is published as one document with a fingerprint anyone can check, so it cannot be quietly changed — and officials can be held to it.",
  },
  {
    title: "Every use of AI is visible",
    body: "AI sorts posts into topics and suggests sources. It does not write for you, vote, or decide anything. Every AI action is listed on a public page, and every post shows how much AI was involved.",
  },
  {
    title: "Built for California residents",
    body: "Every account declares a California home city and county, and every published result reports how many voters were at each verification level. Stronger proof of residency is planned; until it exists, we say so.",
  },
  {
    title: "Your name is yours to show or hide",
    body: "We ask for your real name to protect the integrity of the vote. You choose whether the public sees it or a display name, and you can delete your account and your personal information at any time.",
  },
];

/**
 * A signed-in visitor never sees the pitch — they go straight to `/home`
 * (ARCHITECTURE.md §9). The refresh cookie is `Path=/` with no `Domain`
 * override (backend/routers/auth.py), so it is scoped to the host name and
 * sent to this frontend server on any port of that same host, letting a
 * Server Component check for it without a round trip to the API.
 */
export default async function LandingPage() {
  const cookieStore = await cookies();
  if (cookieStore.get("refresh_token")) {
    redirect("/home");
  }

  return (
    <>
      <header className="page-header">
        <div className="mx-auto max-w-2xl px-4 py-8 text-center sm:py-12">
          <h1 className="text-2xl font-bold sm:text-3xl">
            Your community decides. Your representatives hear it.
          </h1>
          <p className="mt-3 text-base text-[var(--muted)] sm:text-lg">
            Direct Democracy CA is a free public tool for California
            residents. Write down a problem, work out the fix with your
            neighbors, vote on it, and send the result to the people who
            represent you.
          </p>
          <div className="mt-6 flex flex-col items-center gap-3">
            <Link
              href="/signup"
              className="btn btn-primary px-10 py-3 text-lg no-underline"
            >
              Join
            </Link>
            <Link href="/home" className="text-sm no-underline">
              See what people are working on
            </Link>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-4xl px-4 py-8">
        <ol className="grid gap-4 sm:grid-cols-2">
          {ITEMS.map((item, index) => (
            <li key={item.title} className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">
                {index + 1}
              </p>
              <h2 className="mt-1 font-bold">{item.title}</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">{item.body}</p>
            </li>
          ))}
        </ol>

        <p className="mt-10 text-sm text-[var(--muted)]">
          The rules, the settings, and every administrator action are public.{" "}
          <Link href="/settings">Settings</Link> ·{" "}
          <Link href="/ai/actions">AI actions</Link> ·{" "}
          <Link href="/admin/log">Administrator log</Link>
        </p>
      </div>
    </>
  );
}
