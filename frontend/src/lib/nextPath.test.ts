import { test } from "node:test";
import assert from "node:assert/strict";
import { safeNextPath } from "./nextPath";

test("a same-site path is returned as-is", () => {
  assert.equal(safeNextPath("/admin"), "/admin");
});

test("the site root is accepted", () => {
  assert.equal(safeNextPath("/"), "/");
});

test("a path with query and hash is returned parsed", () => {
  assert.equal(safeNextPath("/posts/12?x=1#s"), "/posts/12?x=1#s");
});

test("a plain same-site path is accepted", () => {
  assert.equal(safeNextPath("/ballot"), "/ballot");
});

test("a percent-encoded control character stays a path", () => {
  assert.equal(safeNextPath("/%09/evil.example"), "/%09/evil.example");
});

test("a single backslash is rejected (the browser reads it as //)", () => {
  assert.equal(safeNextPath("/\\evil.example"), null);
});

test("a double backslash is rejected", () => {
  assert.equal(safeNextPath("/\\\\evil.example"), null);
});

test("a real tab character is rejected", () => {
  assert.equal(safeNextPath("/\t/evil.example"), null);
});

test("a real newline character is rejected", () => {
  assert.equal(safeNextPath("/\n/evil.example"), null);
});

test("a protocol-relative address is rejected", () => {
  assert.equal(safeNextPath("//evil.example"), null);
});

test("a triple-slash address is rejected", () => {
  assert.equal(safeNextPath("///evil.example"), null);
});

test("a leading space before a protocol-relative address is rejected", () => {
  assert.equal(safeNextPath(" //evil.example"), null);
});

test("an absolute URL is rejected", () => {
  assert.equal(safeNextPath("https://evil.example"), null);
});

test("a javascript: URL is rejected", () => {
  assert.equal(safeNextPath("javascript:alert(1)"), null);
});

test("missing or empty is rejected", () => {
  assert.equal(safeNextPath(null), null);
  assert.equal(safeNextPath(undefined), null);
  assert.equal(safeNextPath(""), null);
});
