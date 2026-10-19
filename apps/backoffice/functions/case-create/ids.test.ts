import { test } from "node:test";
import assert from "node:assert/strict";
import { generateHash } from "./ids.ts";

test("generateHash is a 22-char base64url string", () => {
  const hash = generateHash();
  assert.match(hash, /^[A-Za-z0-9_-]{22}$/);
  assert.notEqual(hash, generateHash());
});
