import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildPreviewCommunitiesPayload,
  communityKey,
  resolvedChoice,
  resolvedUmbrellaId,
} from "./postPreview";

test("an untouched community with a suggestion keeps it", () => {
  assert.equal(resolvedUmbrellaId(7, undefined), 7);
  assert.equal(resolvedChoice(7, undefined), "keep");
});

test("an untouched community with no suggestion defaults to none of these fit", () => {
  assert.equal(resolvedUmbrellaId(null, undefined), null);
  assert.equal(resolvedChoice(null, undefined), "none");
});

test("choosing a different umbrella overrides the suggestion", () => {
  const decision = { choice: "change" as const, umbrella_id: 9 };
  assert.equal(resolvedUmbrellaId(7, decision), 9);
  assert.equal(resolvedChoice(7, decision), "change");
});

test("choosing a different umbrella overrides even when the AI found none", () => {
  const decision = { choice: "change" as const, umbrella_id: 9 };
  assert.equal(resolvedUmbrellaId(null, decision), 9);
  assert.equal(resolvedChoice(null, decision), "change");
});

test("none of these fit clears the umbrella regardless of the suggestion", () => {
  const decision = { choice: "none" as const, umbrella_id: null };
  assert.equal(resolvedUmbrellaId(7, decision), null);
  assert.equal(resolvedChoice(7, decision), "none");
});

test("building the post payload maps every community independently", () => {
  const communities = [
    { level: "city", entity_id: 1, umbrella_id: 5 },
    { level: "county", entity_id: 2, umbrella_id: null },
    { level: "state", entity_id: 3, umbrella_id: 8 },
  ];
  const decisions = {
    [communityKey("county", 2)]: { choice: "change" as const, umbrella_id: 20 },
    [communityKey("state", 3)]: { choice: "none" as const, umbrella_id: null },
  };
  assert.deepEqual(buildPreviewCommunitiesPayload(communities, decisions), [
    { level: "city", entity_id: 1, umbrella_id: 5 },
    { level: "county", entity_id: 2, umbrella_id: 20 },
    { level: "state", entity_id: 3, umbrella_id: null },
  ]);
});

test("building the post payload keeps every untouched community's suggestion", () => {
  const communities = [
    { level: "city", entity_id: 1, umbrella_id: 5 },
    { level: "county", entity_id: 2, umbrella_id: null },
  ];
  assert.deepEqual(buildPreviewCommunitiesPayload(communities, {}), [
    { level: "city", entity_id: 1, umbrella_id: 5 },
    { level: "county", entity_id: 2, umbrella_id: null },
  ]);
});
