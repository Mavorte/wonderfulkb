import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIntakeLink, generateHash } from "./ids.ts";

test("generateHash is a 22-char base64url string", () => {
  const hash = generateHash();
  assert.match(hash, /^[A-Za-z0-9_-]{22}$/);
  assert.notEqual(hash, generateHash());
});

test("buildIntakeLink appends the hash as ?h=", () => {
  assert.equal(
    buildIntakeLink("https://kb-hackathon.app.sb.wonderful.ai/s/tRQZ3DhKyzWe/", "abc_-1"),
    "https://kb-hackathon.app.sb.wonderful.ai/s/tRQZ3DhKyzWe?h=abc_-1",
  );
});

test("buildIntakeLink is null without a base URL or hash", () => {
  assert.equal(buildIntakeLink("", "abc"), null);
  assert.equal(buildIntakeLink("https://example.com/s/x", null), null);
});
