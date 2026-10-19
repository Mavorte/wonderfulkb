import { test } from "node:test";
import assert from "node:assert/strict";
import { generateCaseId, generateHash } from "./ids.ts";

test("generateCaseId has eight digits and a two-digit year", () => {
  assert.match(generateCaseId(new Date("2026-10-19T00:00:00Z")), /^\d{8}-26$/);
});

test("generateHash is a 22-char base64url string", () => {
  const hash = generateHash();
  assert.match(hash, /^[A-Za-z0-9_-]{22}$/);
  assert.notEqual(hash, generateHash());
});
