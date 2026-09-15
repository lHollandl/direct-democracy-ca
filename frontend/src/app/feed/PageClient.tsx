"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useSession } from "@/components/Session";
import { AiInfluence, Empty, Loading, Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Item = {
  id: number;
  title: string;
  problem_text: string;
  author: string;
  created_at: string;
  label_status: string;
  ai_influence: { label: string; explanation: string };
  communities: { level: string; entity_id: number; umbrella_id: number | null }[];
};

type Payload = {
  ranking: string;
  explanation: string;
  items: Item[];
  filters: Record<string, string | null>;
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

const FILING: Record<string, string> = {
  pending: "Being filed",
  unlabeled: "Waiting to be filed",
  needs_review: "No umbrella covers this yet",
  labeled: "Filed",
};

export default function FeedPage() {
  useDocumentTitle("What people are working on");
  const { me } = useSession();
  const [data, setData] = useState<Payload | null>(null);
  const [community, setCommunity] = useState("");
  const [category, setCategory] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (community) params.set("community", community);
    if (category) params.set("category", category);
    const query = params.toString();
    void get<Payload>(`/feed${query ? `?${query}` : ""}`)
      .then(setData)
      .catch(() => setData(null));
  }, [community, category]);

  return (
    <>
      <PageHeader
        title="What people are working on"
        lead="Every problem someone has written down, with what they think should be done about it."
      />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <form className="flex flex-wrap gap-4" aria-label="Filter the feed">
          <div>
            <label htmlFor="community" className="block text-sm font-medium">Community</label>
            <select
              id="community"
              className="field mt-1"
              value={community}
              onChange={(e) => setCommunity(e.target.value)}
            >
              <option value="">
                {me ? "My three communities" : "Everywhere"}
              </option>
              {(me?.home_communities ?? []).map((c) => (
                <option key={`${c.level}:${c.entity_id}`} value={`${c.level}:${c.entity_id}`}>
                  {c.label}
                </option>
              ))}
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

        {data ? (
          <>
            <Notice>
              <strong>{data.ranking}:</strong> {data.explanation}
            </Notice>
            {data.items.length === 0 ? (
              <div className="mt-4">
                <Empty>
                  Nothing here yet.{" "}
                  <Link href="/posts/new">Write down the first problem</Link>.
                </Empty>
              </div>
            ) : (
              <ol className="mt-4 space-y-3">
                {data.items.map((item) => (
                  <li key={item.id} className="card p-4">
                    <h2 className="font-bold">
                      <Link href={`/posts/${item.id}`}>{item.title}</Link>
                    </h2>
                    <p className="mt-1 text-sm">{item.problem_text}</p>
                    <p className="mt-2 text-xs text-[var(--muted)]">
                      {item.author} · {new Date(item.created_at).toLocaleDateString()} ·{" "}
                      {FILING[item.label_status] ?? item.label_status}
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
            )}
          </>
        ) : (
          <Loading what="the feed" />
        )}
      </div>
    </>
  );
}
