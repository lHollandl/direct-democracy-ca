"use client";

/**
 * The administrator page. The settings control is Foundation (F-24); the
 * cycle controls are Iteration (I-27). Everything on this page writes a row to
 * the public administrator log, and the page says so.
 */

import Link from "next/link";
import { useRef, useState } from "react";
import { get, post } from "@/lib/api";
import { useSession } from "@/components/Session";
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
  const { me, loading } = useSession();
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

  if (loading) return <Loading what="the administrator page" />;
  if (!me?.is_admin) {
    return (
      <>
        <PageHeader title="Administrator controls" />
        <div className="mx-auto max-w-md px-4 py-8">
          <Notice>
            This page is for administrators. Everything they do is published in the{" "}
            <Link href="/admin/log">administrator log</Link>, which anybody can read.
          </Notice>
        </div>
      </>
    );
  }

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

  return (
    <>
      <PageHeader
        title="Administrator controls"
        lead="Everything on this page is written to the public administrator log, with what changed and why."
      />
      <div className="mx-auto max-w-3xl px-4 py-8">
        {message ? <Notice kind="good">{message}</Notice> : null}
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}

        <Section
          title="Change a rule"
          description="Every number that decides an outcome lives here, not in the code. A change takes effect immediately and is public."
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

        {me.home_communities.map((community) => {
          const key = `${community.level}:${community.entity_id}`;
          const list = cycles[key] ?? [];
          const live = list.find((c) => c.state !== "published");
          const step = live ? NEXT_STEP[live.state] : null;
          return (
            <Section key={key} title={`The cycle in ${community.label}`}>
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
                      <button
                        type="button"
                        className="btn"
                        onClick={() => {
                          const reason = window.prompt(
                            "Why is this jury being drawn again? This is published.",
                          );
                          if (reason) void run(`/admin/cycles/${live.id}/redraw-jury`, { reason });
                        }}
                      >
                        Draw a new jury
                      </button>
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
                  <label htmlFor={`refs-${key}`} className="block font-medium">
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

        <Section title="File a post again" description="For a post whose filing failed.">
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
      </div>
    </>
  );
}
