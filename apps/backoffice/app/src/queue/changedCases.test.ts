import { test } from "node:test";
import assert from "node:assert/strict";
import changedCases from "./changedCases.ts";
import type { TriagedCase } from "./triage.ts";

const row = (case_id: string, status: TriagedCase["status"]) => ({ case_id, status }) as TriagedCase;

test("changedCases lists the cases whose status moved since the last list", () => {
  const changed = changedCases(
    [row("a", "evaluating"), row("b", "open"), row("gone", "open")],
    [row("a", "awaiting_decision"), row("b", "open"), row("new", "open")],
  );
  assert.deepEqual([...changed], ["a"]);
});

test("changedCases marks nothing on the first list", () => {
  assert.equal(changedCases(undefined, [row("a", "open")]).size, 0);
});
