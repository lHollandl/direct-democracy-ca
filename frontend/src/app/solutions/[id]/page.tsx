"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { get } from "@/lib/api";
import { useSession } from "@/components/Session";
import { useLoader } from "@/components/useLoader";
import Comments, { Comment } from "@/components/Comments";
import VoteButtons from "@/components/VoteButtons";
import {
  AiInfluence,
  Badge,
  BackLink,
  Empty,
  Explainer,
  Loading,
  Notice,
  PageHeader,
  Section,
} from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type Version = {
  version: number;
  text: string;
  written_by: string;
  from_amendment_id: number | null;
  content_hash: string;
  created_at: string;
};

type Solution = {
  id: number;
  umbrella: { id: number; name: string };
  community: { level: string; entity_id: number; label: string };
  text: string;
  current_version: number;
  author: string;
  net_score: number;
  my_vote: number | null;
  supporters: number;
  is_dominant: boolean;
  dominant_threshold: number;
  ballot_threshold: number;
  absorption_threshold: number;
  on_track_for_ballot: boolean;
  last_ballot_result: string | null;
  last_ballot_version: number | null;
  return_rule_note: string;
  ownership_note: string;
  versions: Version[];
  amendments: {
    id: number;
    author: string;
    rationale: string;
    status: string;
    absorbed_as_version: number | null;
    net_score: number;
    proposed_text: string;
  }[];
  discussion: Comment[];
  discussion_note: string | null;
  ai_influence: { label: string; explanation: string };
};

export default function SolutionPage() {
  useDocumentTitle("A solution");
  const { id } = useParams<{ id: string }>();
  const { me } = useSession();
  const { data, reload } = useLoader<Solution>(
    () => get<Solution>(`/solutions/${id}`),
    [id],
  );

  if (!data) return <Loading what="this solution" />;

  const canAct =
    (me?.email_verified ?? false) &&
    (me?.home_communities.some(
      (c) => c.level === data.community.level && c.entity_id === data.community.entity_id,
    ) ??
      false);

  return (
    <>
      <PageHeader title={`A solution in ${data.umbrella.name}`} lead={data.community.label} />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <BackLink href={`/umbrellas/${data.umbrella.id}`}>Back to the workshop</BackLink>

        <Section title="The text as it stands now">
          <p className="whitespace-pre-line">{data.text}</p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
            <span>Started by {data.author}</span>
            <span>· version {data.current_version}</span>
            {data.is_dominant ? <Badge>dominant</Badge> : null}
            {data.on_track_for_ballot ? <Badge>on track for the ballot</Badge> : null}
            {data.last_ballot_result ? <Badge>{data.last_ballot_result.replace("_", " ")}</Badge> : null}
          </p>
          <div className="mt-3">
            {canAct ? (
              <VoteButtons
                targetType="solution"
                targetId={data.id}
                netScore={data.net_score}
                myVote={data.my_vote}
                label="this solution"
                onChanged={reload}
              />
            ) : (
              <p className="font-bold">Net score {data.net_score}</p>
            )}
          </div>
          <AiInfluence influence={data.ai_influence} />
          <Explainer title="Where this stands against the rules">
            <ul className="list-disc pl-5">
              <li>Dominant at a net score of {data.dominant_threshold}.</li>
              <li>On track for the ballot at {data.ballot_threshold}.</li>
              <li>
                {data.supporters} {data.supporters === 1 ? "person supports" : "people support"} it, so an
                amendment is absorbed at a net score of {data.absorption_threshold}.
              </li>
            </ul>
            <p className="mt-2">{data.ownership_note}</p>
            {data.last_ballot_result ? <p className="mt-2">{data.return_rule_note}</p> : null}
          </Explainer>
        </Section>

        <Section title="Every version, kept" description="Each version has its own fingerprint. Nothing is overwritten.">
          <ol className="space-y-3">
            {data.versions.map((version) => (
              <li key={version.version} className="card p-3">
                <p className="text-sm font-medium">
                  Version {version.version} · written by {version.written_by}
                  {version.from_amendment_id ? " · from an amendment" : ""}
                </p>
                <p className="mt-1 whitespace-pre-line text-sm">{version.text}</p>
                <p className="mt-1 break-all text-xs text-[var(--muted)]">
                  Fingerprint: {version.content_hash}
                </p>
              </li>
            ))}
          </ol>
        </Section>

        <Section title="Amendments">
          {data.amendments.length === 0 ? (
            <Empty>
              {data.is_dominant
                ? "Nobody has proposed a change yet."
                : "Amendments open once a solution becomes dominant."}
            </Empty>
          ) : (
            <ol className="space-y-3">
              {data.amendments.map((amendment) => (
                <li key={amendment.id} className="card p-3">
                  <p className="text-sm font-medium">
                    {amendment.author} · <Badge>{amendment.status.replace("_", " ")}</Badge>
                    {amendment.absorbed_as_version
                      ? ` · became version ${amendment.absorbed_as_version}`
                      : ""}
                  </p>
                  <p className="mt-1 text-sm italic">“{amendment.rationale}”</p>
                  <p className="mt-1 whitespace-pre-line text-sm">{amendment.proposed_text}</p>
                  <p className="mt-1 text-sm font-bold">Net score {amendment.net_score}</p>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-3 text-sm">
            Propose a change from the{" "}
            <Link href={`/umbrellas/${data.umbrella.id}`}>workshop page</Link>.
          </p>
        </Section>

        <Section title="Discussion">
          {data.discussion_note ? (
            <Notice>{data.discussion_note}</Notice>
          ) : (
            <Comments
              targetType="solution"
              targetId={data.id}
              comments={data.discussion}
              canWrite={canAct}
              onPosted={reload}
            />
          )}
        </Section>
      </div>
    </>
  );
}
