"use client";

/**
 * The administrator page. The settings control is Foundation (F-24); the
 * cycle controls are Iteration (I-27). Everything on this page writes a row to
 * the public administrator log, and the page says so.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState, type ReactNode } from "react";
import { get, post } from "@/lib/api";
import { useRequireAuth } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import { Badge, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Setting = { key: string; value: unknown; meaning: string };
type Cycle = { id: number; number: number; state: string };
type Umbrella = { id: number; name: string };

const NEXT_STEP: Record<string, { action: string; label: string } | null> = {
  workshop: null,
  prepared: { action: "publish", label: "Publish the empty summary" },
  jury_review: { action: "open", label: "Open the ballot" },
  open: { action: "close", label: "Close the ballot" },
  closed: { action: "publish", label: "Publish the summary" },
  published: null,
};

export default function AdminPage() {
  useDocumentTitle("Administrator controls");
  const pathname = usePathname();
  const auth = useRequireAuth();
  const me = auth.status === "authed" ? auth.me : null;
  const [message, setMessage] = useState<string | null>(null);
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const settingFormRef = useRef<HTMLFormElement>(null);
  const relabelFormRef = useRef<HTMLFormElement>(null);
  const { data, reload } = useLoader<{
    settings: Setting[];
    cycles: Record<string, Cycle[]>;
    umbrellas: Record<string, Umbrella[]>;
  }>(async () => {
    if (!me?.is_admin) return { settings: [], cycles: {}, umbrellas: {} };
    const payload = await get<{ settings: Setting[] }>("/settings");
    const cycles: Record<string, Cycle[]> = {};
    const umbrellas: Record<string, Umbrella[]> = {};
    for (const community of me.home_communities) {
      const key = `${community.level}:${community.entity_id}`;
      try {
        cycles[key] = (
          await get<{ cycles: Cycle[] }>(
            `/communities/${community.level}/${community.entity_id}/cycles`,
          )
        ).cycles;
        umbrellas[key] = (
          await get<{ umbrellas: Umbrella[] }>(`/umbrellas?community=${key}`)
        ).umbrellas;
      } catch {
        cycles[key] = [];
      }
    }
    return { settings: payload.settings, cycles, umbrellas };
  }, [me]);
  const settings = data?.settings ?? [];
  const cycles = data?.cycles ?? {};
  const umbrellas = data?.umbrellas ?? {};

  async function run(
    path: string,
    body?: unknown,
    description?: string,
    form?: HTMLFormElement | null,
  ) {
    clear();
    setMessage(null);
    try {
      await post(path, body);
      setMessage(description ?? "Done. It is in the public administrator log.");
      reload();
    } catch (problem) {
      fail(problem, form);
    }
  }

  let body: ReactNode;
  if (auth.status === "loading" || auth.status === "redirecting") {
    body = <Loading what="the administrator page" />;
  } else if (auth.status === "expired") {
    body = (
      <Notice kind="bad">
        You have been signed out.{" "}
        <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Sign in again.</Link>
      </Notice>
    );
  } else if (!me?.is_admin) {
    body = (
      <Notice>
        This page is for administrators. Everything they do is published in the{" "}
        <Link href="/admin/log">administrator log</Link>, which anybody can read.
      </Notice>
    );
  } else {
    const you = me;
    body = (
      <>
        {message ? <Notice kind="good">{message}</Notice> : null}
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}

        <Section
          title="Change a rule"
          description="Every number that decides a democratic outcome — thresholds, timers, sizes — lives here, not in the code. Use it when a public setting genuinely needs to change, such as trying a full cycle the same day (see 'Run a cycle' below). A change takes effect immediately and is written to the public administrator log with the reason you give."
        >
          <form
            ref={settingFormRef}
            className="card space-y-3 p-3"
            noValidate
            onSubmit={async (event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              await run(
                "/admin/settings",
                {
                  key: form.get("key"),
                  value: form.get("value"),
                  reason: form.get("reason"),
                },
                "Changed. It is on the settings page and in the administrator log.",
                settingFormRef.current,
              );
            }}
          >
            <div>
              <label htmlFor="key" className="block font-medium">Rule</label>
              <select id="key" name="key" required className="field mt-1" {...fieldProps("key")}>
                {settings.map((setting) => (
                  <option key={setting.key} value={setting.key}>
                    {setting.key} (now {String(setting.value)})
                  </option>
                ))}
              </select>
              <FieldError name="key" fieldErrors={fieldErrors} />
            </div>
            <div>
              <label htmlFor="value" className="block font-medium">New value</label>
              <input
                id="value"
                name="value"
                required
                className="field mt-1"
                {...fieldProps("value")}
              />
              <FieldError name="value" fieldErrors={fieldErrors} />
            </div>
            <div>
              <label htmlFor="reason" className="block font-medium">Why</label>
              <input
                id="reason"
                name="reason"
                required
                minLength={3}
                className="field mt-1"
                {...fieldProps("reason", "reason-hint")}
              />
              <FieldError name="reason" fieldErrors={fieldErrors} />
              <p id="reason-hint" className="mt-1 text-sm text-[var(--muted)]">
                Published with the change. Write it for the community, not for yourself.
              </p>
            </div>
            <button type="submit" className="btn btn-primary">Change it</button>
          </form>
        </Section>

        <Section
          title="Run a cycle"
          description="Moves one community's ballot cycle forward, one step at a time. Use it when that community's workshop is ready for a ballot, or to close and publish one already open. Every transition is written to the public administrator log."
        >
          <ol className="list-decimal space-y-1 pl-5 text-sm text-[var(--muted)]">
            <li>Prepare — freezes what qualified and, if anything did, draws a jury.</li>
            <li>Jury review — the drawn jury may hold items back, in public, with a reason.</li>
            <li>Open — the ballot accepts votes.</li>
            <li>Close — voting stops; the result is tallied.</li>
            <li>Publish — the result becomes a public document with a fingerprint.</li>
          </ol>
          <p className="mt-2 text-sm text-[var(--muted)]">
            To try a full cycle the same day, set <code>ballot_min_dominant_days</code>{" "}
            to 0 above, with a reason — and set it back afterward, with a reason,
            so dominance keeps requiring real time to prove itself.
          </p>
        </Section>

        {you.home_communities.map((community) => {
          const key = `${community.level}:${community.entity_id}`;
          const list = cycles[key] ?? [];
          const live = list.find((c) => c.state !== "published");
          const step = live ? NEXT_STEP[live.state] : null;
          return (
            <Section
              key={key}
              title={`The cycle in ${community.label}`}
              description="The one control that advances this community's own cycle through the five steps above. Use it once that community's workshop, jury, or ballot is ready for its next step."
            >
              {live ? (
                <div className="card p-3">
                  <p>
                    Cycle {live.number} · <Badge>{live.state.replace("_", " ")}</Badge>
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {step ? (
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => void run(`/admin/cycles/${live.id}/${step.action}`)}
                      >
                        {step.label}
                      </button>
                    ) : null}
                    {live.state === "jury_review" ? (
                      <div>
                        <p className="text-sm text-[var(--muted)]">
                          Replaces the current jury with a fresh draw. Use it only if
                          the draw needs to be redone — for example, an eligibility
                          rule was fixed after this draw ran. The reason you give is
                          published; the old draw stays inspectable, never deleted.
                        </p>
                        <button
                          type="button"
                          className="btn mt-1"
                          onClick={() => {
                            const reason = window.prompt(
                              "Why is this jury being drawn again? This is published.",
                            );
                            if (reason) void run(`/admin/cycles/${live.id}/redraw-jury`, { reason });
                          }}
                        >
                          Draw a new jury
                        </button>
                      </div>
                    ) : null}
                    <Link href={`/cycles/${live.id}`} className="btn no-underline">
                      See the ballot
                    </Link>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() =>
                    void run("/admin/cycles/prepare", {
                      level: community.level,
                      entity_id: community.entity_id,
                    })
                  }
                >
                  Prepare a ballot for {community.label}
                </button>
              )}

              {umbrellas[key]?.length ? (
                <div className="mt-4">
                  <p className="text-sm text-[var(--muted)]">
                    Asks AI to suggest up to a public limit of reference sources
                    for one umbrella's discussion. Use it when an umbrella could
                    use outside sources and none have been added yet. Every
                    suggestion is a labeled AI action, in the public log, and
                    members still decide whether each one is useful.
                  </p>
                  <label htmlFor={`refs-${key}`} className="mt-2 block font-medium">
                    Ask AI to suggest references for an umbrella
                  </label>
                  <select
                    id={`refs-${key}`}
                    className="field mt-1"
                    defaultValue=""
                    onChange={(event) => {
                      if (event.target.value) {
                        void run(
                          `/admin/umbrellas/${event.target.value}/recommend-references`,
                        );
                        event.target.value = "";
                      }
                    }}
                  >
                    <option value="">Choose an umbrella</option>
                    {umbrellas[key].map((umbrella) => (
                      <option key={umbrella.id} value={umbrella.id}>
                        {umbrella.name}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Needs a web search provider to be configured. Until one is,
                    this answers honestly that it cannot run.
                  </p>
                </div>
              ) : null}
            </Section>
          );
        })}

        <Section
          title="File a post again"
          description="Retries AI labeling for one post by number. Use it for a post stuck 'not filed yet' sooner than the automatic retry, or after fixing whatever kept the AI unreachable. Written to the public administrator log."
        >
          <form
            ref={relabelFormRef}
            className="flex items-end gap-2"
            noValidate
            onSubmit={async (event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              await run(
                `/admin/posts/${form.get("post_id")}/relabel`,
                undefined,
                undefined,
                relabelFormRef.current,
              );
            }}
          >
            <div>
              <label htmlFor="post_id" className="block font-medium">Post number</label>
              <input
                id="post_id"
                name="post_id"
                type="number"
                required
                className="field mt-1"
                {...fieldProps("post_id")}
              />
              <FieldError name="post_id" fieldErrors={fieldErrors} />
            </div>
            <button type="submit" className="btn">Try filing it again</button>
          </form>
        </Section>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Administrator controls"
        lead={
          me?.is_admin
            ? "Everything on this page is written to the public administrator log, with what changed and why."
            : undefined
        }
      />
      <div className={`mx-auto px-4 py-8 ${me?.is_admin ? "max-w-3xl" : "max-w-md"}`}>{body}</div>
    </>
  );
}
