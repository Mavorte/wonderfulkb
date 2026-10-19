// Generates the eval cases' files from cases.ts:
// - <agent-functions>/functions/shared/fixtures/eval-cases.json: the mock-eval-*
//   fixtures the agent-functions mock layer serves, in the upstream API formats;
// - evals/scenarios/<slug>.json: one backoffice_eval scenario per case, with its
//   answer key as table_assertions;
// - evals/batches/*.json.
//
// Usage: node eval-cases/build.ts <agent-functions checkout> [--check]
// --check writes nothing and fails if a generated file is out of date.

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { type Area, CASES, type EvalCase, type Fixture, REAL_CASE_SCENARIOS } from "./cases.ts";
import type { CaseDocument } from "./documents.ts";

const ROOT = resolve(import.meta.dirname, "..");
const EVALUATIONS_TABLE = "agent_functions.case_evaluations";
const RESULTS_TABLE = "agent_functions.case_evaluation_results";

// Every tool runs for real; the fixtures stand in for the APIs.
const TOOLS = Object.keys(JSON.parse(readFileSync(join(ROOT, "config.json"), "utf8")).behavior.global_tools);

// One seed row per table, so the eval's in-memory copies know their columns.
const TABLE_FIXTURES = {
  [EVALUATIONS_TABLE]: [
    {
      evaluation_id: "ev-fixture-seed",
      case_id: "fixture-seed",
      status: "completed",
      verdict: "ready",
      summary: "Seed row so the eval table copy knows its columns.",
      rules_total: 3,
      is_mock: true,
      started_at: "2026-10-19T00:00:00Z",
      finished_at: "2026-10-19T00:00:01Z",
    },
  ],
  [RESULTS_TABLE]: [
    {
      evaluation_id: "ev-fixture-seed",
      rule_id: "loan_agreement_present",
      case_id: "fixture-seed",
      status: "passed",
      expected: "Smlouva o úvěru",
      found: "seed.pdf",
      sources: "[]",
      details: null,
      reasoning: "Seed row.",
      recorded_at: "2026-10-19T00:00:00Z",
    },
  ],
};

// The fixture in the formats of the case/client API and the documents API.
// Documents are listed by key into a table shared by all cases, because most
// cases reuse the clean case's documents.
function toUpstream(fixture: Fixture, table: Record<string, unknown>) {
  const documents = fixture.documents.map((d) => {
    const upstream = toUpstreamDocument(d);
    const key = `${d.document_id}-${createHash("sha1").update(JSON.stringify(upstream)).digest("hex").slice(0, 8)}`;
    table[key] = upstream;
    return key;
  });
  return {
    case: {
      case_id: fixture.case_id,
      client_id: fixture.client?.client_id ?? "00000000-0000-4000-8000-000000000000",
      status: "open",
      created_at: "2026-10-19T09:00:00Z",
      metadata: { loan_number: "170555/25", asset: "Pásové rypadlo Volvo EC220E", serial_number: "VCEC220EV00312345" },
    },
    client: fixture.client,
    ...(fixture.errors && { errors: fixture.errors }),
    documents,
  };
}

function toUpstreamDocument(d: CaseDocument) {
  return {
    document_id: d.document_id,
    title: d.title,
    label: d.label,
    processing_status: "completed",
    page_count: d.pages.length,
    text: d.pages.join("\f"),
    confidence: d.confidence,
    pages_failed: d.pages_failed,
    // Only the signature fields the adapter reads; the rest are optional upstream.
    signatures: d.signatures.map((s, i) => ({
      signature_id: `sig_${d.document_id}_${String(i + 1).padStart(2, "0")}`,
      page: s.page,
      role: s.role,
      role_evidence: s.evidence,
      copy_suspicion: { level: "none", matches: [] },
    })),
    ...(d.errors && { errors: d.errors }),
  };
}

function tableAssertions(c: EvalCase) {
  const results = Object.entries(c.expected ?? {}).map(([rule_id, status]) => ({
    table: RESULTS_TABLE,
    where: { case_id: c.case_id, rule_id },
    values: { status },
  }));
  if (!c.case_id) return results;
  const where = { case_id: c.case_id };
  const run =
    c.run === "none" ? { table: EVALUATIONS_TABLE, where, exists: false }
    : { table: EVALUATIONS_TABLE, where, values: { status: c.run, ...(c.verdict && { verdict: c.verdict }) } };
  return [run, ...results];
}

function scenario(c: EvalCase) {
  return {
    schema_version: 1,
    name: c.name,
    description: `${c.description} Generated from eval-cases/cases.ts.`,
    channel: "backoffice",
    eval_type: "backoffice_eval",
    instructions: {
      mode: "turn_based",
      backoffice_task: {
        task_type: "case_evaluation",
        trigger_type: "manual_chat",
        task_input: c.task_input ?? JSON.stringify({ case_id: c.case_id }),
        context: {},
        passthrough_tools: TOOLS,
        ...(c.final_status && { expected_final_status: c.final_status }),
        max_execution_time_seconds: c.max_seconds ?? 900,
        expected_behavior: c.behavior,
        table_assertions: tableAssertions(c),
      },
      turns: [],
      table_fixtures: TABLE_FIXTURES,
    },
  };
}

const slugs = (area: Area) => CASES.filter((c) => c.area === area).map((c) => c.slug);

const BATCHES = {
  case_evaluation: {
    name: "Case evaluation: full suite",
    description: "Every scenario: the real case bundles, and the synthetic cases for each rule, verdict and failure path.",
    scenario_slugs: [...REAL_CASE_SCENARIOS, ...CASES.map((c) => c.slug)],
  },
  // Required check on every pull request (.wonderful/actions/workflows/ci_pull_request.yml):
  // one scenario per outcome, so it stays short.
  ci_pull_request: {
    name: "CI: pull request",
    description: "The critical outcomes, all at once: ready, needs_correction with chained defects, needs_review, a failed run, and the unhappy real bundle.",
    scenario_slugs: ["clean_case_ready", "multiple_defects", "signatures_unavailable", "documents_api_down", "unhappy_recipient_ico"],
  },
  case_evaluation_real_cases: {
    name: "Case evaluation: real case bundles",
    description: "The Solom Rec, Stavby Fišer and unhappy bundles, and an unknown case.",
    scenario_slugs: REAL_CASE_SCENARIOS,
  },
  case_evaluation_agreement_rules: {
    name: "Case evaluation: agreement rules",
    description: "Loan agreement presence, required documents matching and the recipient against the client record.",
    scenario_slugs: [...slugs("baseline"), ...slugs("agreement")],
  },
  case_evaluation_contents_rules: {
    name: "Case evaluation: document contents rules",
    description: "Missing fields, missing signatures, blank and unreadable pages, and signatures that could not be loaded.",
    scenario_slugs: [...slugs("baseline"), ...slugs("contents")],
  },
  case_evaluation_robustness: {
    name: "Case evaluation: robustness",
    description: "Task input without JSON or without a case ID, an instruction inside a document, a cross-document mismatch, and failing APIs.",
    scenario_slugs: [...slugs("robustness"), "unknown_case"],
  },
};

const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;

function main() {
  const [functionsDir, ...flags] = process.argv.slice(2);
  if (!functionsDir) {
    console.error("Usage: node eval-cases/build.ts <agent-functions checkout> [--check]");
    process.exit(2);
  }
  const check = flags.includes("--check");
  const documents: Record<string, unknown> = {};
  const cases = CASES.flatMap((c) => (c.fixture ? [toUpstream(c.fixture, documents)] : []));
  const files: Array<[string, string]> = [
    [
      join(resolve(functionsDir), "functions/shared/fixtures/eval-cases.json"),
      json({
        generated_by: "case-evaluator eval-cases/build.ts; edit eval-cases/cases.ts and regenerate instead of editing this file",
        cases,
        documents,
      }),
    ],
    ...CASES.map((c): [string, string] => [join(ROOT, "evals/scenarios", `${c.slug}.json`), json(scenario(c))]),
    // Every scenario of a batch runs at once: one takes 1-10 minutes, so a batch takes about as long as its slowest scenario.
    ...Object.entries(BATCHES).map(([slug, batch]): [string, string] => [
      join(ROOT, "evals/batches", `${slug}.json`),
      json({ schema_version: 1, ...batch, max_parallel_evaluations: batch.scenario_slugs.length }),
    ]),
  ];
  const stale = files.filter(([path, content]) => {
    try {
      return readFileSync(path, "utf8") !== content;
    } catch {
      return true;
    }
  });
  if (check) {
    for (const [path] of stale) console.error(`out of date: ${path}`);
    process.exit(stale.length ? 1 : 0);
  }
  for (const [path, content] of stale) writeFileSync(path, content);
  console.log(`${files.length} files, ${stale.length} written`);
}

main();
