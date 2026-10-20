import { test } from "node:test";
import assert from "node:assert/strict";
import { createCaseView, focusSourceOf, groupSources, problemsOf, toSource, type EvaluationRow, type ResultRow } from "./evaluation.ts";
import { focusOn, visibleMarks } from "./focus.ts";

// Cut from evaluation ev-SYN-A01-mvggfzga-v9g6.
const TRANSFER = "4958e179-0f22-52a4-9d0a-7979e73b6667";
const LOAN = "34fcd896-107a-583f-a406-6a8100cf8150";

const evaluation: EvaluationRow = { evaluation_id: "ev-1", case_id: "SYN-A01", status: "completed" };

function row(rule_id: string, status: string, sources: unknown[]): ResultRow {
  return { evaluation_id: "ev-1", case_id: "SYN-A01", rule_id, status, reasoning: "", sources: JSON.stringify(sources) };
}

const transfer = row("security_transfer_contents", "missing", [
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 1, role: "evidence", field: "creditor", region_id: "p1-r07", bbox: [0.378, 0.1718, 0.5569, 0.1819], quote: "98000110", anchor: "lines" },
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 2, role: "evidence", field: "transfer_terms", quote: "Dočasný převod", anchor: "page_only" },
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 6, role: "evidence" },
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 6, role: "missing_value", issue: "recipient signature", region_id: "p6-r22", bbox: [0.5048, 0.5258, 0.5939, 0.5351], quote: "Matěj Vřesník", anchor: "region" },
]);

const required = row("required_documents_present", "missing", [
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf" },
  { document_id: LOAN, title: "00_Smlouva_o_uveru.pdf", page: 2, role: "declaration", issue: "faktura", region_id: "p2-r19", bbox: [0.0672, 0.5017, 0.9017, 0.5406], quote: "Před čerpáním…", anchor: "region" },
  { document_id: LOAN, title: "00_Smlouva_o_uveru.pdf", page: 2, role: "declaration", issue: "doklad o úhradě", region_id: "p2-r19", bbox: [0.0672, 0.5017, 0.9017, 0.5406], quote: "Před čerpáním…", anchor: "region" },
]);

const conflict = row("recipient_consistent", "conflict", [
  { document_id: LOAN, title: "00_Smlouva_o_uveru.pdf", page: 1, role: "compare_a", field: "ico", bbox: [0.3, 0.2, 0.4, 0.21], quote: "98001001", anchor: "lines" },
  { document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 1, role: "compare_b", field: "ico", bbox: [0.3, 0.26, 0.4, 0.27], quote: "98001002", anchor: "lines" },
  { document_id: LOAN, title: "00_Smlouva_o_uveru.pdf", page: 4, role: "compare_a", field: "ico", bbox: [0.3, 0.5, 0.4, 0.51], quote: "98001001", anchor: "lines" },
]);

test("toSource keeps the box only for lines and region anchors with a page", () => {
  const raw = { document_id: TRANSFER, title: "a.pdf", page: 1, bbox: [0.1, 0.2, 0.3, 0.4] };
  assert.equal(toSource({ ...raw, anchor: "lines" }, "r", 0)?.anchor, "lines");
  // A missing anchor with a bbox is drawn as a region.
  assert.equal(toSource(raw, "r", 0)?.anchor, "region");
  assert.equal(toSource({ ...raw, anchor: "page_only" }, "r", 0)?.bbox, undefined);
  assert.equal(toSource({ ...raw, page: null }, "r", 0)?.bbox, undefined);
  // Out-of-range values are clamped; empty or malformed boxes are dropped.
  assert.deepEqual(toSource({ ...raw, bbox: [-0.1, 0.2, 1.2, 0.4] }, "r", 0)?.bbox, [0, 0.2, 1, 0.4]);
  assert.equal(toSource({ ...raw, bbox: [0.3, 0.2, 0.1, 0.4] }, "r", 0)?.anchor, "page_only");
  assert.equal(toSource({ ...raw, bbox: [0.1, 0.2, 0.3] }, "r", 0)?.bbox, undefined);
  assert.equal(toSource({ document_id: TRANSFER, title: null }, "r", 0), null);
});

test("rows recorded before regions are page-only references", () => {
  const legacy = toSource({ document_id: TRANSFER, title: "02_Zajistovaci_prevod.pdf", page: 3 }, "r", 0)!;
  assert.equal(legacy.anchor, "page_only");
  assert.equal(legacy.problem, false);
  assert.equal(legacy.docKey, TRANSFER);
});

test("problem classification follows issue and role", () => {
  const problem = (raw: object) => toSource({ title: "a.pdf", ...raw }, "r", 0)!.problem;
  assert.equal(problem({ role: "evidence" }), false);
  assert.equal(problem({}), false);
  assert.equal(problem({ role: "evidence", issue: "IČO" }), true);
  assert.equal(problem({ role: "compare_b" }), true);
  assert.equal(problem({ role: "declaration" }), true);
  assert.equal(problem({ role: "missing_value" }), true);
});

test("documents are keyed by document_id and collect their boxes", () => {
  const renamed = row("loan_agreement_present", "passed", [{ document_id: LOAN, title: "00_Smlouva_renamed.pdf", page: 1 }]);
  const view = createCaseView(evaluation, [transfer, required, renamed]);
  assert.deepEqual(view.docs.map((d) => d.key), [LOAN, TRANSFER]);
  const transferDoc = view.docs.find((d) => d.key === TRANSFER)!;
  assert.deepEqual(transferDoc.referencedPages, [1, 2, 6]);
  assert.deepEqual(transferDoc.marks.map((m) => m.source.regionId), ["p1-r07", "p6-r22"]);
  assert.equal(transferDoc.marks[1].status, "fail");
  // A source without an id falls back to its title, and joins a document of that title that has one.
  assert.equal(toSource({ title: "x.pdf" }, "r", 0)?.docKey, "title:x.pdf");
  const withoutId = row("handover_protocol_contents", "passed", [{ title: "02_Zajistovaci_prevod.pdf", page: 4 }]);
  const merged = createCaseView(evaluation, [transfer, withoutId]);
  assert.deepEqual(merged.docs.map((d) => [d.key, d.referencedPages]), [[TRANSFER, [1, 2, 4, 6]]]);
});

test("problemsOf groups compare sides by field and keeps other problems apart", () => {
  const view = createCaseView(evaluation, [conflict, required, transfer]);
  const rule = (id: string) => view.rules.find((r) => r.id === id)!;

  const [ico] = problemsOf(rule("recipient_consistent"));
  assert.equal(ico.kind, "compare");
  assert.equal(ico.label, "ico");
  assert.deepEqual(ico.sides.map((s) => [s.side, s.sources.map((x) => x.quote)]), [
    ["a", ["98001001", "98001001"]],
    ["b", ["98001002"]],
  ]);

  assert.deepEqual(problemsOf(rule("required_documents_present")).map((p) => [p.kind, p.label]), [
    ["declaration", "faktura"],
    ["declaration", "doklad o úhradě"],
  ]);
  assert.deepEqual(problemsOf(rule("security_transfer_contents")).map((p) => [p.kind, p.label]), [["missing_value", "recipient signature"]]);
});

test("opening a rule or a document lands on a box when there is one", () => {
  const view = createCaseView(evaluation, [transfer, required]);
  const rule = view.rules.find((r) => r.id === "security_transfer_contents")!;
  assert.equal(focusSourceOf(rule)?.regionId, "p6-r22");
  const [cited] = groupSources(rule.sources);
  assert.deepEqual(cited.pages, [1, 2, 6]);
  assert.equal(cited.first.regionId, "p1-r07");
  // required_documents_present: the first source has no page; the chip opens the cited page instead.
  const [, loan] = groupSources(view.rules.find((r) => r.id === "required_documents_present")!.sources);
  assert.equal(loan.first.page, 2);
});

test("evidence boxes show only for the selected rule; problems of failing rules always", () => {
  const view = createCaseView(evaluation, [transfer, required]);
  const transferDoc = view.docs.find((d) => d.key === TRANSFER)!;
  const loanDoc = view.docs.find((d) => d.key === LOAN)!;

  assert.deepEqual(visibleMarks(transferDoc.marks, 1, null), []);
  assert.equal(visibleMarks(transferDoc.marks, 6, null)[0].mark.source.regionId, "p6-r22");

  const creditor = transferDoc.marks[0].source;
  const shown = visibleMarks(transferDoc.marks, 1, focusOn(creditor));
  assert.deepEqual(shown.map((s) => s.mark.source.id), [creditor.id]);

  // Two declarations on the same clause share one box that names both.
  const [clause] = visibleMarks(loanDoc.marks, 2, null);
  assert.equal(visibleMarks(loanDoc.marks, 2, null).length, 1);
  assert.match(clause.label, /faktura[\s\S]*doklad o úhradě/);
});
