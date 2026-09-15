import Link from "next/link";
import { PageHeader } from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * `jury_size` decides a democratic status and so must never be a constant in
 * copy (CLAUDE.md Law 8) — it is read from the public settings, the same
 * value every other page uses. `null` on a fetch failure, so the sentence
 * below can fall back to wording that carries no number rather than a stale
 * one (audit demo-01 run 4, LOW).
 */
async function citizensDrawnForJury(): Promise<number | null> {
  try {
    const response = await fetch(`${API_BASE}/settings`, { cache: "no-store" });
    if (!response.ok) return null;
    const body: { settings: { key: string; value: unknown }[] } = await response.json();
    const row = body.settings.find((setting) => setting.key === "jury_size");
    return typeof row?.value === "number" ? row.value : null;
  } catch {
    return null;
  }
}

export default async function Home() {
  const jurySize = await citizensDrawnForJury();
  return (
    <>
      <PageHeader
        title="The tools that only well-funded political organisations have had"
        lead="Write down a problem in your community. Propose what should be done about it. Work on it with your neighbours, vote on it, and send the result to the people who represent you — in a form they cannot dispute."
      />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <ol className="grid gap-4 sm:grid-cols-2">
          {[
            {
              step: "1",
              title: "Say what is wrong, and what to do",
              body: "Nothing can be posted here without at least one proposed solution. This is not a place to complain.",
            },
            {
              step: "2",
              title: "Work on it together",
              body: "Solutions that enough neighbours support become open to amendment. Anyone can propose a better wording; enough support and it becomes the text.",
            },
            {
              step: "3",
              title:
                jurySize !== null
                  ? `${jurySize} neighbours check it over`
                  : "Neighbours check it over",
              body:
                jurySize !== null
                  ? `Before a ballot, ${jurySize} residents drawn at random look at what qualified. They cannot change anything. They can hold something back, in public, with a reason.`
                  : "Before a ballot, residents drawn at random — see the settings page for how many — look at what qualified. They cannot change anything. They can hold something back, in public, with a reason.",
            },
            {
              step: "4",
              title: "The community votes, and the result is published",
              body: "One vote each, counted the same. The result is a public page with a fingerprint anyone can check, and one button that emails it to your representatives from your own address.",
            },
          ].map((item) => (
            <li key={item.step} className="card p-4">
              <p className="text-sm font-bold text-[var(--accent)]">Step {item.step}</p>
              <h2 className="mt-1 font-bold">{item.title}</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">{item.body}</p>
            </li>
          ))}
        </ol>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/signup" className="btn btn-primary no-underline">
            Join your community
          </Link>
          <Link href="/feed" className="btn no-underline">
            See what people are working on
          </Link>
        </div>

        <section className="mt-10">
          <h2 className="text-xl font-bold">What we promise, and what we cannot</h2>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <strong>Every rule is public.</strong> Every number that decides an
              outcome is on the <Link href="/settings">settings page</Link>, with
              what it means and when it last changed.
            </li>
            <li>
              <strong>AI never decides anything.</strong> It sorts and suggests,
              it is labelled every time, and every action it takes is in the{" "}
              <Link href="/ai/actions">public log</Link>. You can correct it.
            </li>
            <li>
              <strong>Your ballot vote is yours alone.</strong> Not other voters,
              not administrators. Everyone else sees totals.
            </li>
            <li>
              <strong>We cannot check that you live where you say.</strong> Every
              published result says so, plainly, so nobody is misled about what
              the numbers mean.
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
