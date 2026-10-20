import { describe, expect, it } from "vitest";
import { recordRule } from "./record";
import { checkLoanAgreement } from "./rules/loanAgreement";
import { RULE_IDS } from "./rules";
import { checkRequiredDocuments, toTypedRequirements } from "./rules/requiredDocuments";
import {
  EVALUATIONS_TABLE,
  RESULTS_TABLE,
  finishRun,
  getDocumentRead,
  getRequirements,
  getRun,
  getStatuses,
  saveDocumentRead,
  saveRequirements,
  startRun,
} from "./run";
import { RUN, createTestContext } from "./testContext";

const { evaluation_id: _, row_id: __, ...runInput } = RUN;

describe("evaluation run", () => {
  it("opens a running row and keeps the run in KV", async () => {
    const { ctx, tables } = createTestContext();
    expect(getRun(ctx)).toBeNull();
    const run = await startRun(ctx, runInput);
    expect(getRun(ctx)?.evaluation_id).toBe(run.evaluation_id);
    expect(run.evaluation_id).toMatch(/^ev-mock-unhappy-[0-9a-z]+-[0-9a-z]+$/);
    expect(tables[EVALUATIONS_TABLE][0].data).toMatchObject({ case_id: "mock-unhappy", status: "running", rules_total: 19, is_mock: true });
  });

  it("writes a pending row per rule with its category", async () => {
    const { ctx, tables } = createTestContext();
    const run = await startRun(ctx, runInput);
    expect(tables[RESULTS_TABLE].map((r) => r.data.rule_id)).toEqual(RULE_IDS);
    expect(tables[RESULTS_TABLE].every((r) => r.data.status === "pending" && r.data.evaluation_id === run.evaluation_id)).toBe(true);
    expect(tables[RESULTS_TABLE].find((r) => r.data.rule_id === "client_status_valid")?.data.category).toBe("client_status");
    expect(await getStatuses(ctx, run)).toEqual({});
  });

  it("writes one result row per rule and replaces it when recorded again", async () => {
    const { ctx, tables } = createTestContext();
    const run = await startRun(ctx, runInput);
    await recordRule(ctx, (r) => checkLoanAgreement(r, { status: "missing", reasoning: "first" }));
    const second = await recordRule(ctx, (r) => checkLoanAgreement(r, { status: "passed", document_id: "agr", reasoning: "second" }));
    expect(second).toMatchObject({ accepted: true, status: "passed" });
    expect(tables[RESULTS_TABLE]).toHaveLength(RULE_IDS.length);
    const row = tables[RESULTS_TABLE].find((r) => r.data.rule_id === "loan_agreement_present")!;
    expect(row.data).toMatchObject({ category: "completeness", status: "passed", reasoning: "second", case_id: "mock-unhappy" });
    expect(JSON.parse(row.data.sources)).toEqual([{ document_id: "agr", title: "0_Form_Smlouva.pdf" }]);
    expect(await getStatuses(ctx, run)).toEqual({ loan_agreement_present: "passed" });
  });

  it("writes nothing for a rejected input", async () => {
    const { ctx, tables } = createTestContext();
    await startRun(ctx, runInput);
    const outcome = await recordRule(ctx, (r) => checkLoanAgreement(r, { status: "passed", reasoning: "x" }));
    expect(outcome.accepted).toBe(false);
    expect(tables[RESULTS_TABLE].every((r) => r.data.status === "pending")).toBe(true);
  });

  it("refuses to record without a run", async () => {
    const { ctx } = createTestContext();
    expect((await recordRule(ctx, (r) => checkLoanAgreement(r, { status: "missing", reasoning: "x" }))).accepted).toBe(false);
  });

  it("keeps the typed requirements after required_documents_present is saved", async () => {
    const { ctx } = createTestContext();
    const run = await startRun(ctx, runInput);
    expect(getRequirements(ctx, run)).toBeNull();
    const requirements = [{ description: "objednávka", type: "purchase_contract" as const, document_id: "ord" }, { description: "faktura", type: "invoice" as const }];
    await recordRule(ctx, (r) => checkRequiredDocuments(r, { status: "missing", requirements, reasoning: "x" }), (r, result) => saveRequirements(ctx, r, toTypedRequirements(result.details)));
    expect(getRequirements(ctx, run)).toEqual([{ type: "purchase_contract", document_id: "ord" }, { type: "invoice", document_id: null }]);
  });

  it("keeps each document read under the run", async () => {
    const { ctx } = createTestContext();
    const run = await startRun(ctx, runInput);
    const read = { page_count: 2, empty_pages: [2], pages_failed: [], confidence: 0.9, signatures: [{ role: "borrower", page: 1 }] };
    saveDocumentRead(ctx, run, "ord", read);
    expect(getDocumentRead(ctx, run, "ord")).toEqual(read);
    expect(getDocumentRead(ctx, run, "agr")).toBeNull();
    expect(getDocumentRead(ctx, { ...run, evaluation_id: "ev-other" }, "ord")).toBeNull();
  });

  it("refuses to finish while rules are still pending", async () => {
    const { ctx } = createTestContext();
    await startRun(ctx, runInput);
    await recordRule(ctx, (r) => checkLoanAgreement(r, { status: "passed", document_id: "agr", reasoning: "x" }));
    const finish = (await import("../tools/finish_evaluation/index.ts")).default;
    const outcome = await finish.handler(ctx as any, { summary: "done" });
    expect(outcome.accepted).toBe(false);
    expect(outcome.problems[0]).toContain("required_documents_present");
    expect(outcome.problems[0]).not.toContain("loan_agreement_present");
  });

  it("closes the run with its verdict", async () => {
    const { ctx, tables } = createTestContext();
    const run = await startRun(ctx, runInput);
    await finishRun(ctx, run, "completed", "done", "needs_correction");
    expect(tables[EVALUATIONS_TABLE][0].data).toMatchObject({ status: "completed", verdict: "needs_correction", summary: "done" });
  });
});
