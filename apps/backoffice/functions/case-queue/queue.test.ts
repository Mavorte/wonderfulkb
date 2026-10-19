import { test } from "node:test";
import assert from "node:assert/strict";
import { createQueue, latestEvaluations } from "./queue.ts";

const client = { client_id: "c1", ico: "98007106", name: "Agroluh Vřesava s.r.o.", status: "active", kyc: { status: "ok" } };
const awsCase = { case_id: "SYN-A01", client_id: "c1", status: "open", created_at: "2026-10-19T09:00:00Z" };
const run = { evaluation_id: "ev1", case_id: "SYN-A01", status: "completed", verdict: "needs_correction", started_at: "2026-10-19T19:00:00Z" };

test("latestEvaluations keeps the newest real run per case and skips mock runs", () => {
  const latest = latestEvaluations([
    { ...run, evaluation_id: "old", started_at: "2026-10-19T17:00:00Z" },
    { ...run, evaluation_id: "new" },
    { ...run, evaluation_id: "mock", started_at: "2026-10-19T20:00:00Z", is_mock: true },
    { ...run, evaluation_id: "mock-only", case_id: "mock-unhappy", is_mock: true },
  ]);
  assert.deepEqual([...latest.values()].map((e) => e.evaluation_id), ["new"]);
});

test("createQueue lists each evaluated case with its client and only the rules that did not pass", () => {
  const [queued] = createQueue(
    latestEvaluations([run]),
    [
      { evaluation_id: "ev1", rule_id: "invoice_contents", status: "missing", found: "No invoice", reasoning: "Not uploaded" },
      { evaluation_id: "ev1", rule_id: "loan_agreement_present", status: "passed", reasoning: "Found" },
      { evaluation_id: "ev1", rule_id: "guarantee_contents", status: "not_applicable", reasoning: "Not required" },
      { evaluation_id: "other", rule_id: "invoice_contents", status: "conflict", reasoning: "Other run" },
    ],
    new Map([["SYN-A01", awsCase]]),
    [client],
  );
  assert.equal(queued.case_found, true);
  assert.equal(queued.created_at, "2026-10-19T09:00:00Z");
  assert.deepEqual(queued.client, { name: "Agroluh Vřesava s.r.o.", ico: "98007106", kyc_status: "ok" });
  assert.deepEqual(
    queued.evaluation.issues.map((i) => [i.rule_id, i.status]),
    [["invoice_contents", "missing"]],
  );
});

test("createQueue keeps a run whose case the case API does not know", () => {
  const [queued] = createQueue(latestEvaluations([run]), [], new Map(), [client]);
  assert.equal(queued.case_found, false);
  assert.equal(queued.client, null);
  assert.equal(queued.status, "open");
});
