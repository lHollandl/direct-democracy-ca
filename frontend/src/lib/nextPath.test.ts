import { test } from "node:test";
import assert from "node:assert/strict";
import { safeNextPath } from "./nextPath";

test("a same-site path is returned as-is", () => {
  assert.equal(safeNextPath("/admin"), "/admin");
});

test("a protocol-relative address is rejected", () => {
  assert.equal(safeNextPath("//evil.example"), null);
});

test("an absolute URL is rejected", () => {
  assert.equal(safeNextPath("https://evil.example"), null);
});

test("missing or empty is rejected", () => {
  assert.equal(safeNextPath(null), null);
  assert.equal(safeNextPath(undefined), null);
  assert.equal(safeNextPath(""), null);
});
