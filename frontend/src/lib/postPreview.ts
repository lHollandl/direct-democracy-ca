/**
 * Pure decision-to-payload mapping for step 4 of "New post"
 * (DEMOCRACY.md §4.1, as amended by change/02 fix-1's FX-01).
 *
 * There is no "keep" decision: an untouched community has no entry in the
 * decisions map at all, and posting without touching either button keeps
 * the AI's suggestion — because posting is the decision.
 */

export type PreviewCommunity = {
  level: string;
  entity_id: number;
  umbrella_id: number | null;
};

export type PreviewDecision = { choice: "change" | "none"; umbrella_id: number | null };

export function communityKey(level: string, entityId: number): string {
  return `${level}:${entityId}`;
}

/** The umbrella id that would actually be posted for one community. */
export function resolvedUmbrellaId(
  suggestedUmbrellaId: number | null,
  decision: PreviewDecision | undefined,
): number | null {
  if (!decision) return suggestedUmbrellaId;
  return decision.choice === "none" ? null : decision.umbrella_id;
}

/** The three states the "current choice" line reports:
 * "keep" — the AI's suggestion, untouched; "change" — the author's own pick;
 * "none" — none of these fit (either chosen, or the AI found nothing). */
export function resolvedChoice(
  suggestedUmbrellaId: number | null,
  decision: PreviewDecision | undefined,
): "keep" | "change" | "none" {
  if (decision) return decision.choice;
  return suggestedUmbrellaId !== null ? "keep" : "none";
}

/** The `communities[]` body of `POST /posts` for `category_choice: "preview"`. */
export function buildPreviewCommunitiesPayload(
  communities: PreviewCommunity[],
  decisions: Record<string, PreviewDecision>,
): { level: string; entity_id: number; umbrella_id: number | null }[] {
  return communities.map((c) => {
    const key = communityKey(c.level, c.entity_id);
    return {
      level: c.level,
      entity_id: c.entity_id,
      umbrella_id: resolvedUmbrellaId(c.umbrella_id, decisions[key]),
    };
  });
}
