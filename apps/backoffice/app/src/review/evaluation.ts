// Case-evaluator data for the review screen: rows from agent_functions.case_evaluations
// and agent_functions.case_evaluation_results, mapped into what the page renders.

import { ruleLabels } from "./ruleLabels.ts";

export type CheckStatus = "pass" | "fail" | "warn" | "na";

export interface EvaluationRow {
  evaluation_id: string;
  case_id: string;
  status: string;
  verdict?: string | null;
  summary?: string | null;
  rules_total?: number | null;
  is_mock?: boolean | null;
  started_at?: string | null;
  finished_at?: string | null;
}

// sources and details are JSON strings written by the agent.
export interface ResultRow {
  evaluation_id: string;
  rule_id: string;
  case_id: string;
  status: string;
  expected?: string | null;
  found?: string | null;
  sources?: string | null;
  details?: string | null;
  reasoning: string;
  recorded_at?: string | null;
}

export interface EvaluationPayload {
  evaluation: EvaluationRow | null;
  results: ResultRow[];
}

// [x0, y0, x1, y1] as fractions of the rendered page, origin top left.
export type BBox = [number, number, number, number];

// lines: bbox is tight around the value; region: it covers the paragraph or table row;
// page_only: no box, only the page (scans, values not found in the text, rows recorded before regions).
export type Anchor = "lines" | "region" | "page_only";

export interface SourceRef {
  // `${ruleId}#${index}`, unique within the run.
  id: string;
  ruleId: string;
  docKey: string;
  documentId?: string;
  title: string;
  page?: number;
  regionId?: string;
  bbox?: BBox;
  anchor: Anchor;
  quote?: string;
  // evidence, declaration, missing_value or compare_a, compare_b, …; absent on a plain reference.
  role?: string;
  field?: string;
  issue?: string;
  // Shows a problem (drawn in the rule's status colour) rather than supporting evidence.
  problem: boolean;
}

// Problems of rules that didn't pass take the rule's status colour; everything else is plain evidence.
export function toneOf(source: SourceRef, status: CheckStatus): "fail" | "warn" | "evidence" {
  return source.problem && (status === "fail" || status === "warn") ? status : "evidence";
}

export interface Mark {
  source: SourceRef;
  ruleId: string;
  ruleLabel: string;
  status: CheckStatus;
}

export interface Field {
  field: string;
  value: string | null;
  page: number | null;
}

export interface Signature {
  role: string;
  required: number;
  found: number;
  pages: number[];
}

export interface RequiredDoc {
  description: string;
  type: string;
  title: string | null;
}

export interface RuleView {
  id: string;
  label: string;
  status: CheckStatus;
  rawStatus: string;
  expected: string | null;
  found: string | null;
  reasoning: string;
  recordedAt: string | null;
  sources: SourceRef[];
  fields: Field[];
  signatures: Signature[];
  confidence: number | null;
  requiredDocs: RequiredDoc[];
}

export interface RuleGroup {
  id: number;
  title: string;
  description: string;
  rules: RuleView[];
  // False when the evaluator has no rules for this checklist item yet.
  evaluated: boolean;
  status: CheckStatus;
}

export interface DocView {
  key: string;
  // The documents API id, when the agent recorded it.
  documentId?: string;
  title: string;
  // pages[i] is page i + 1; null when that page has no preview.
  pages: (string | null)[];
  pdf?: string;
  // Why there is no preview, once the documents API has answered.
  unavailable?: string;
  // The documents API has the readable original (revealed only on request).
  originalAvailable?: boolean;
  // The documents API hasn't answered yet.
  loading?: boolean;
  fields: Field[];
  referencedPages: number[];
  status?: CheckStatus;
  // Every source on this document that has a box.
  marks: Mark[];
}

export interface FixItem {
  ruleId: string;
  label: string;
  found: string | null;
  status: CheckStatus;
}

export interface CaseView {
  evaluation: EvaluationRow;
  groups: RuleGroup[];
  rules: RuleView[];
  docs: DocView[];
  missingDocs: RequiredDoc[];
  fixes: FixItem[];
  facts: { label: string; value: string | null }[];
  borrower: string | null;
  ico: string | null;
  loanNo: string | null;
  decision: "approve" | "return" | "reject" | null;
  headline: string;
}

const statusMap: Record<string, CheckStatus> = {
  passed: "pass",
  missing: "fail",
  conflict: "fail",
  failed: "fail",
  cannot_verify: "warn",
  not_applicable: "na",
};

// The business-rules checklist; evaluator rules are filed under the item they serve.
const checklist: { id: number; title: string; description: string; ruleIds: string[] }[] = [
  {
    id: 1,
    title: "Document completeness and validity",
    description:
      "All required documents are present, readable, signed where necessary, and within the bank's accepted age or expiry limits.",
    ruleIds: [
      "loan_agreement_present",
      "required_documents_present",
      "handover_protocol_contents",
      "insurance_vinculation_contents",
      "security_transfer_contents",
      "guarantee_contents",
      "payment_proof_contents",
      "technical_specification_contents",
    ],
  },
  {
    id: 2,
    title: "Consistency across documents",
    description:
      "Company name, registration number, address and applicant details match across the application, registry extract, accounts and purchase documents.",
    ruleIds: ["recipient_matches_client"],
  },
  {
    id: 3,
    title: "Company existence and status",
    description:
      "The business exists in an official register and its legal status permits borrowing; flag dissolution, liquidation or insolvency.",
    ruleIds: [],
  },
  {
    id: 4,
    title: "Ownership and control",
    description:
      "Trace ownership to the ultimate beneficial owners, verify relevant identities and reconcile discrepancies with ownership records.",
    ruleIds: [],
  },
  {
    id: 5,
    title: "Sanctions and financial-crime screening",
    description:
      "Screen the business and relevant individuals for sanctions, politically exposed person status and adverse information.",
    ruleIds: [],
  },
  {
    id: 6,
    title: "Supplier and purchase-document verification",
    description:
      "The supplier is legitimate; quotation or invoice names the correct buyer, identifies the equipment and supports the requested amount.",
    ruleIds: ["purchase_contract_contents", "invoice_contents"],
  },
];

// Rendered pages exist only for the SOLOM pack used by the mock-solom-rec case,
// served from dev/public, so previews are a local-development aid only.
const previewCase = "mock-solom-rec";
const previewBase = "/mock-case/R000096444";
const previewsByPrefix: Record<string, { name: string; count: number; pad?: number }> = {
  "0": { name: "00-loan-contract", count: 4 },
  "1": { name: "01-general-terms", count: 19, pad: 2 },
  "2": { name: "02-security-transfer", count: 6 },
  "3": { name: "03-insurance-assignment", count: 2 },
  "4": { name: "04-guarantee", count: 3 },
  "9": { name: "09-payment-agreement", count: 4 },
  "10": { name: "10-purchase-order", count: 2 },
  "11": { name: "11-handover-protocol", count: 4 },
};

function previewFor(caseId: string, title: string): { pages: string[]; pdf: string } | null {
  // import.meta.env is undefined outside Vite (node --test).
  if (!import.meta.env?.DEV || caseId !== previewCase) return null;
  const prefix = String(Number(title.split("_")[0]));
  const p = previewsByPrefix[prefix];
  if (!p) return null;
  const pages = Array.from(
    { length: p.count },
    (_, i) => `${previewBase}/${p.name}-${String(i + 1).padStart(p.pad ?? 1, "0")}.jpg`,
  );
  return { pages, pdf: `${previewBase}/${p.name}.pdf` };
}

function parseJson<T>(raw: string | null | undefined): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

interface DocDetails {
  document_id?: string;
  fields?: Field[];
  signatures?: Signature[];
  confidence?: number;
}

type RawSource = {
  document_id?: string | null;
  title?: string | null;
  page?: number | null;
  region_id?: string | null;
  bbox?: unknown;
  quote?: string | null;
  role?: string | null;
  field?: string | null;
  issue?: string | null;
  anchor?: string | null;
};

// Documents are matched by their API id; the title is only a fallback for sources without one.
function docKeyOf(documentId: string | null | undefined, title: string): string {
  return documentId || `title:${title}`;
}

function toBBox(raw: unknown): BBox | undefined {
  if (!Array.isArray(raw) || raw.length !== 4 || !raw.every((n) => typeof n === "number" && Number.isFinite(n))) return undefined;
  const [x0, y0, x1, y1] = raw.map((n: number) => Math.min(1, Math.max(0, n)));
  return x1 > x0 && y1 > y0 ? [x0, y0, x1, y1] : undefined;
}

function isProblemRole(role: string | undefined): boolean {
  return !!role && (role.startsWith("compare_") || role === "declaration" || role === "missing_value");
}

export function toSource(raw: RawSource, ruleId: string, index: number): SourceRef | null {
  if (!raw.title) return null;
  const page = raw.page ?? undefined;
  // A box needs its page; anchor page_only (and rows recorded before regions) never draw one.
  const bbox = page && raw.anchor !== "page_only" ? toBBox(raw.bbox) : undefined;
  const role = raw.role ?? undefined;
  const issue = raw.issue ?? undefined;
  return {
    id: `${ruleId}#${index}`,
    ruleId,
    docKey: docKeyOf(raw.document_id, raw.title),
    documentId: raw.document_id ?? undefined,
    title: raw.title,
    page,
    regionId: raw.region_id ?? undefined,
    bbox,
    anchor: bbox ? (raw.anchor === "lines" ? "lines" : "region") : "page_only",
    quote: raw.quote ?? undefined,
    role,
    field: raw.field ?? undefined,
    issue,
    problem: !!issue || isProblemRole(role),
  };
}

const severity: Record<CheckStatus, number> = { na: 0, pass: 1, warn: 2, fail: 3 };

export function worst(statuses: CheckStatus[]): CheckStatus {
  return statuses.reduce<CheckStatus>((w, s) => (severity[s] > severity[w] ? s : w), "na");
}

function toRule(row: ResultRow): RuleView {
  const details = parseJson<DocDetails | RequiredDoc[]>(row.details);
  const docDetails = details && !Array.isArray(details) ? details : null;
  const raw = parseJson<RawSource[]>(row.sources);
  const sources = (Array.isArray(raw) ? raw : [])
    .map((s, i) => toSource(s ?? {}, row.rule_id, i))
    .filter((s): s is SourceRef => !!s);
  return {
    id: row.rule_id,
    label: ruleLabels[row.rule_id] ?? row.rule_id.replace(/_/g, " "),
    status: statusMap[row.status] ?? "warn",
    rawStatus: row.status,
    expected: row.expected ?? null,
    found: row.found ?? null,
    reasoning: row.reasoning,
    recordedAt: row.recorded_at ?? null,
    sources,
    fields: docDetails?.fields ?? [],
    signatures: docDetails?.signatures ?? [],
    confidence: docDetails?.confidence ?? null,
    requiredDocs: Array.isArray(details) ? details : [],
  };
}

function firstField(rules: RuleView[], names: string[]): string | null {
  for (const name of names) {
    for (const rule of rules) {
      const hit = rule.fields.find((f) => f.field === name && f.value);
      if (hit?.value) return hit.value;
    }
  }
  return null;
}

// "Name s.r.o., IČO 123" → "Name s.r.o. · 123"
function party(value: string | null): string | null {
  return value?.replace(/,\s*IČO?:?\s*/, " · ") ?? null;
}

export interface CitedDoc {
  docKey: string;
  title: string;
  pages: number[];
  // Where opening the document lands: its first source with a box, else its first source.
  first: SourceRef;
}

// One entry per document, with every cited page.
export function groupSources(sources: SourceRef[]): CitedDoc[] {
  const byDoc = new Map<string, CitedDoc>();
  for (const s of sources) {
    const entry = byDoc.get(s.docKey) ?? { docKey: s.docKey, title: s.title, pages: [], first: s };
    if (s.page && !entry.pages.includes(s.page)) entry.pages.push(s.page);
    if ((s.bbox && !entry.first.bbox) || (s.page && !entry.first.page)) entry.first = s;
    byDoc.set(s.docKey, entry);
  }
  for (const entry of byDoc.values()) entry.pages.sort((a, b) => a - b);
  return [...byDoc.values()];
}

export interface Problem {
  key: string;
  kind: "compare" | "missing_value" | "declaration" | "issue";
  // The field or requirement the places show, e.g. "ico", "recipient signature", "faktura".
  label: string;
  // Compare sides in letter order (a is the reference); other kinds have one side, "".
  sides: { side: string; sources: SourceRef[] }[];
}

// A rule's problem places, one entry per field or issue.
export function problemsOf(rule: RuleView): Problem[] {
  const byKey = new Map<string, Problem>();
  for (const s of rule.sources.filter((src) => src.problem)) {
    const compare = s.role?.match(/^compare_(\w+)$/);
    const kind: Problem["kind"] = compare ? "compare" : s.role === "missing_value" || s.role === "declaration" ? s.role : "issue";
    const label = (kind === "compare" ? (s.field ?? s.issue) : (s.issue ?? s.field)) ?? "value";
    const key = `${kind}:${label}`;
    const problem = byKey.get(key) ?? { key, kind, label, sides: [] };
    const side = compare?.[1] ?? "";
    const entry = problem.sides.find((x) => x.side === side);
    if (entry) entry.sources.push(s);
    else problem.sides.push({ side, sources: [s] });
    byKey.set(key, problem);
  }
  for (const p of byKey.values()) p.sides.sort((a, b) => a.side.localeCompare(b.side));
  return [...byKey.values()];
}

// Where opening a rule lands: a problem with a box, any problem, a source with a box, any source.
export function focusSourceOf(rule: RuleView): SourceRef | undefined {
  const { sources } = rule;
  return (
    sources.find((s) => s.problem && s.bbox) ??
    sources.find((s) => s.problem) ??
    sources.find((s) => s.bbox) ??
    sources[0]
  );
}

export function shortTitle(title: string) {
  return title.replace(/\.pdf$/i, "").replace(/^\d+_/, "").replace(/_/g, " ");
}

const verdicts: Record<string, { decision: CaseView["decision"]; headline: string }> = {
  needs_correction: { decision: "return", headline: "Return for corrections — hold disbursement" },
  ready: { decision: "approve", headline: "Ready for disbursement" },
  approved: { decision: "approve", headline: "Ready for disbursement" },
  rejected: { decision: "reject", headline: "Reject" },
};

export function createCaseView(evaluation: EvaluationRow, results: ResultRow[]): CaseView {
  const rules = results.map(toRule);
  const byId = new Map(rules.map((r) => [r.id, r]));
  const filed = new Set(checklist.flatMap((c) => c.ruleIds));

  const groups: RuleGroup[] = checklist.map((c) => {
    const groupRules = c.ruleIds.map((id) => byId.get(id)).filter((r): r is RuleView => !!r);
    // Rules the checklist doesn't know yet still show up under completeness.
    if (c.id === 1) groupRules.push(...rules.filter((r) => !filed.has(r.id)));
    return {
      id: c.id,
      title: c.title,
      description: c.description,
      rules: groupRules,
      evaluated: c.ruleIds.length > 0 && groupRules.length > 0,
      status: worst(groupRules.map((r) => r.status)),
    };
  });

  // A source without document_id joins the document of the same title that has one.
  const idByTitle = new Map<string, string>();
  for (const s of rules.flatMap((r) => r.sources)) if (s.documentId) idByTitle.set(s.title, s.documentId);
  for (const s of rules.flatMap((r) => r.sources)) {
    const id = idByTitle.get(s.title);
    if (!s.documentId && id) s.docKey = id;
  }

  const docs = new Map<string, DocView>();
  for (const rule of rules) {
    for (const s of rule.sources) {
      const doc =
        docs.get(s.docKey) ??
        ({ key: s.docKey, title: s.title, pages: [], fields: [], referencedPages: [], marks: [], ...previewFor(evaluation.case_id, s.title) } as DocView);
      doc.documentId ??= s.documentId;
      if (s.page && !doc.referencedPages.includes(s.page)) doc.referencedPages.push(s.page);
      if (s.bbox) doc.marks.push({ source: s, ruleId: rule.id, ruleLabel: rule.label, status: rule.status });
      // required_documents_present cites the documents that are there, so it doesn't mark them.
      if (rule.id !== "required_documents_present" && rule.status !== "pass" && rule.status !== "na") {
        doc.status = worst([doc.status ?? "na", rule.status]);
      }
      docs.set(s.docKey, doc);
    }
    // Extracted fields belong to the document the content rule read.
    if (rule.fields.length && rule.sources[0]) {
      const doc = docs.get(rule.sources[0].docKey);
      if (doc && !doc.fields.length) doc.fields = rule.fields;
    }
  }
  for (const doc of docs.values()) doc.referencedPages.sort((a, b) => a - b);

  const missingDocs = (byId.get("required_documents_present")?.requiredDocs ?? []).filter((d) => !d.title);
  const fixes = rules
    .filter((r) => r.status === "fail" || r.status === "warn")
    .map((r) => ({ ruleId: r.id, label: r.label, found: r.found, status: r.status }));

  const recipient = byId.get("recipient_matches_client");
  const borrowerParty = recipient?.expected ?? firstField(rules, ["debtor", "buyer", "policyholder"]);
  const borrower = borrowerParty?.split(/,\s*IČO?\b/)[0] ?? null;
  const ico = borrowerParty?.match(/IČO?:?\s*(\d+)/)?.[1] ?? null;
  const loanNo = firstField(rules, ["secured_contract"])?.replace(/^Smlouva o úvěru č\.\s*/, "") ?? null;

  const verdict = verdicts[evaluation.verdict ?? ""];
  const headline =
    evaluation.status === "failed"
      ? "Evaluation failed"
      : evaluation.status !== "completed"
        ? "Checking business rules"
        : (verdict?.headline ?? evaluation.verdict ?? "No verdict");

  return {
    evaluation,
    groups,
    rules,
    docs: [...docs.values()].sort((a, b) => Number(a.title.split("_")[0]) - Number(b.title.split("_")[0])),
    missingDocs,
    fixes,
    facts: [
      { label: "Borrower", value: party(borrowerParty) },
      { label: "Loan contract", value: loanNo },
      { label: "Asset", value: firstField(rules, ["asset", "subject", "insured_asset"]) },
      { label: "Serial number", value: firstField(rules, ["serial_number"]) },
      { label: "Supplier", value: party(firstField(rules, ["seller", "handed_over_by"])) },
      { label: "Guarantor", value: party(firstField(rules, ["guarantor"])) },
    ],
    borrower,
    ico,
    loanNo,
    decision: evaluation.status === "completed" ? (verdict?.decision ?? null) : null,
    headline,
  };
}

export function isRunning(evaluation: EvaluationRow): boolean {
  return evaluation.status !== "completed" && evaluation.status !== "failed";
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("cs-CZ", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(start: string | null | undefined, end: string | null | undefined): string | null {
  if (!start || !end) return null;
  const s = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000);
  return s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`;
}
