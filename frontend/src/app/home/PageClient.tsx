"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useSession } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import { AiInfluence, Empty, Loading, Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";
import { useSettingsMap } from "@/content/explainers";
import {
  BallotPanel,
  JuryPanel,
  PinnedBallotBlock,
  type CycleEntry,
  type PinnedBallot,
} from "./Panels";

type Item = {
  id: number;
  title: string;
  problem_text: string;
  author: string;
  created_at: string;
  label_status: string;
  ai_influence: { label: string; explanation: string };
  vote_count: number;
  comment_count: number;
  communities: { level: string; entity_id: number; umbrella_id: number | null }[];
};

type FeedPayload = {
  ranking: string;
  sort: string;
  explanation: string;
  items: Item[];
  next_cursor: string | null;
  filters: Record<string, unknown>;
};

const CATEGORIES = [
  ["", "Every category"],
  ["roads_and_infrastructure", "Roads and Infrastructure"],
  ["housing_and_homelessness", "Housing and Homelessness"],
  ["public_safety", "Public Safety"],
  ["environmental_issues", "Environmental Issues"],
  ["education", "Education"],
  ["public_transit", "Public Transit"],
  ["water_and_utilities", "Water and Utilities"],
  ["parks_and_recreation", "Parks and Recreation"],
  ["economic_development", "Economic Development"],
  ["government_accountability", "Government Accountability"],
];

const SORTS: [string, string][] = [
  ["newest", "Newest"],
  ["oldest", "Oldest"],
  ["most_votes", "Most votes"],
  ["most_comments", "Most comments"],
];

/**
 * DEMOCRACY.md §4.1 — the three honest filing states, each its own sentence
 * (CLAUDE.md §2). This is the compact, aggregate wording for a feed card
 * spanning all of a post's communities; the per-community detail — with the
 * community and main-category names — is on the post's own page.
 */
function filingWords(status: string, labelRetryMinutes: number | null): string {
  if (status === "pending") return "Being filed — the AI is reading this now";
  if (status === "unlabeled") {
    return labelRetryMinutes !== null
      ? `Not filed yet — the AI could not be reached. The platform tries again every ${labelRetryMinutes} minutes`
      : "Not filed yet — the AI could not be reached. The platform tries again shortly";
  }
  if (status === "needs_review") return "Not filed — no umbrella covers this yet in one of its communities";
  if (status === "labeled") return "Filed";
  return status;
}

const SHOW_BALLOT_KEY = "ddca.home.showBallot";

function useShowBallotSwitch(): [boolean, (value: boolean) => void] {
  const [show, setShow] = useState(true);
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SHOW_BALLOT_KEY);
      if (stored !== null) setShow(stored === "true");
    } catch {
      // Private browsing or a blocked store: fall back to the default (on).
    }
  }, []);
  const update = (value: boolean) => {
    setShow(value);
    try {
      window.localStorage.setItem(SHOW_BALLOT_KEY, String(value));
    } catch {
      // Nothing to persist; the page still works for this visit.
    }
  };
  return [show, update];
}

export default function HomePage() {
  useDocumentTitle("Home");
  const { me, loading: sessionLoading } = useSession();
  const settings = useSettingsMap();
  const labelRetryMinutes = settings ? Number(settings.label_retry_minutes) : null;
  const [showBallot, setShowBallot] = useShowBallotSwitch();

  const [community, setCommunity] = useState("");
  const [scope, setScope] = useState<"" | "all">("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("newest");
  const [items, setItems] = useState<Item[]>([]);
  const [payload, setPayload] = useState<FeedPayload | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (community) params.set("community", community);
    else if (scope === "all") params.set("scope", "all");
    if (category) params.set("category", category);
    if (q.trim().length >= 2) params.set("q", q.trim());
    params.set("sort", sort);
    const query = params.toString();
    void get<FeedPayload>(`/feed${query ? `?${query}` : ""}`).then((body) => {
      setPayload(body);
      setItems(body.items);
      setCursor(body.next_cursor);
    });
  }, [community, scope, category, q, sort]);

  async function showMore() {
    if (!cursor) return;
    const params = new URLSearchParams();
    if (community) params.set("community", community);
    else if (scope === "all") params.set("scope", "all");
    if (category) params.set("category", category);
    if (q.trim().length >= 2) params.set("q", q.trim());
    params.set("sort", sort);
    params.set("cursor", cursor);
    const body = await get<FeedPayload>(`/feed?${params.toString()}`);
    setItems((prev) => [...prev, ...body.items]);
    setCursor(body.next_cursor);
  }

  const { data: mine } = useLoader<{ communities: CycleEntry[] } | null>(async () => {
    if (!me) return null;
    return get<{ communities: CycleEntry[] }>("/cycles/mine");
  }, [me]);

  const { data: pinnedBallots, reload: reloadPinned } = useLoader<PinnedBallot[]>(async () => {
    if (!mine) return [];
    const open = mine.communities.filter((entry) => entry.cycle?.state === "open");
    const found: PinnedBallot[] = [];
    for (const entry of open) {
      try {
        const ballot = await get<{
          cycle_id: number;
          community: { label: string };
          you_can_vote: boolean;
          items: PinnedBallot["items"];
        }>(`/cycles/${entry.cycle!.id}/ballot`);
        found.push({
          cycle_id: ballot.cycle_id,
          community_label: ballot.community.label,
          you_can_vote: ballot.you_can_vote,
          items: ballot.items,
        });
      } catch {
        // A ballot that can't be read right now simply isn't pinned.
      }
    }
    return found;
  }, [mine]);

  return (
    <>
      <PageHeader
        title="Home"
        lead="Every problem someone has written down, with what they think should be done about it."
      />
      <div className="mx-auto max-w-4xl px-4 py-8">
        {!sessionLoading && me && mine ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <BallotPanel entries={mine.communities} />
            <JuryPanel entries={mine.communities} />
          </div>
        ) : null}

        {!sessionLoading && me ? (
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showBallot}
              onChange={(e) => setShowBallot(e.target.checked)}
            />
            Show ballot items here
          </label>
        ) : null}

        {showBallot && pinnedBallots ? (
          <div className="mt-4">
            <PinnedBallotBlock ballots={pinnedBallots} onVoted={reloadPinned} />
          </div>
        ) : null}

        <form className="mt-6 flex flex-wrap items-end gap-4" aria-label="Filter and sort Home">
          <div>
            <label htmlFor="q" className="block text-sm font-medium">Search</label>
            <input
              id="q"
              type="search"
              className="field mt-1"
              placeholder="2 or more characters"
              minLength={2}
              maxLength={100}
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="sort" className="block text-sm font-medium">Sort</label>
            <select
              id="sort"
              className="field mt-1"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              {SORTS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="community" className="block text-sm font-medium">Community</label>
            <select
              id="community"
              className="field mt-1"
              value={scope === "all" ? "all" : community}
              onChange={(e) => {
                if (e.target.value === "all") {
                  setScope("all");
                  setCommunity("");
                } else {
                  setScope("");
                  setCommunity(e.target.value);
                }
              }}
            >
              <option value="">{me ? "My home communities" : "Everywhere"}</option>
              {(me?.home_communities ?? []).map((c) => (
                <option key={`${c.level}:${c.entity_id}`} value={`${c.level}:${c.entity_id}`}>
                  {c.label}
                </option>
              ))}
              <option value="all">All of California</option>
            </select>
          </div>
          <div>
            <label htmlFor="category" className="block text-sm font-medium">Main category</label>
            <select
              id="category"
              className="field mt-1"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </form>

        {payload ? (
          <>
            <Notice>
              <strong>{payload.ranking}:</strong> {payload.explanation}
            </Notice>
            {items.length === 0 ? (
              <div className="mt-4">
                <Empty>
                  Nothing here yet.{" "}
                  <Link href="/posts/new">Write down the first problem</Link>.
                </Empty>
              </div>
            ) : (
              <>
                <ol className="mt-4 space-y-3">
                  {items.map((item) => (
                    <li key={item.id} className="card p-4">
                      <h2 className="font-bold">
                        <Link href={`/posts/${item.id}`}>{item.title}</Link>
                      </h2>
                      <p className="mt-1 text-sm">{item.problem_text}</p>
                      <p className="mt-2 text-xs text-[var(--muted)]">
                        {item.author} · {new Date(item.created_at).toLocaleDateString()} ·{" "}
                        {filingWords(item.label_status, labelRetryMinutes)}
                      </p>
                      <p className="mt-1 text-sm font-medium">
                        {item.vote_count} vote{item.vote_count === 1 ? "" : "s"} ·{" "}
                        {item.comment_count} comment{item.comment_count === 1 ? "" : "s"}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {item.communities
                          .filter((c) => c.umbrella_id)
                          .map((c) => (
                            <Link
                              key={`${c.level}:${c.entity_id}`}
                              href={`/umbrellas/${c.umbrella_id}`}
                              className="badge no-underline"
                            >
                              Open the workshop
                            </Link>
                          ))}
                      </div>
                      <AiInfluence influence={item.ai_influence} />
                    </li>
                  ))}
                </ol>
                {cursor ? (
                  <button type="button" className="btn mt-4" onClick={() => void showMore()}>
                    Show more
                  </button>
                ) : null}
              </>
            )}
          </>
        ) : (
          <Loading what="the feed" />
        )}
      </div>
    </>
  );
}
