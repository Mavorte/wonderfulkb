// Validator shared by the *_consistent rules: one entity (recipient, supplier,
// asset, ...) must show the same values in every document, and agree with its
// reference record where there is one (client record, case record). The agent
// reports the value each document shows, with its page; the tool normalizes
// the values, compares them and checks the agent's status.

import type { RuleId } from "../rules";
import { type DocumentRead, type Locate, type Run, type Source, findDocument } from "../run";
import { type CheckOutcome, rejected, requireReasoning } from "./check";

// How an attribute's values are normalized and checked for format.
export type AttributeKind = "text" | "ico" | "dic" | "account" | "id" | "amount" | "year";

export type AttributeSpec = { key: string; label: string; kind: AttributeKind };

// Values the documents must agree with, and where they come from.
export type Reference = { source: string; values: Partial<Record<string, string>> };

export type ConsistencySpec = {
  rule_id: RuleId;
  entity: string;
  attributes: AttributeSpec[];
  // The entity may be absent from a case (e.g. no guarantor), so not_applicable is allowed.
  optional?: boolean;
  reference?: (run: Run) => Reference | null;
  // Region labels and parties where the entity is named, to place each value (lib/regions.ts).
  regions?: Locate;
};

export type ConsistencyValue = { document_id: string; page?: number; value: string };

export type ConsistencyInput = {
  status: "passed" | "conflict" | "cannot_verify" | "not_applicable";
  attributes?: Array<{ attribute: string; values: ConsistencyValue[] }>;
  // Text attributes whose differing values the agent judges to be the same thing written differently.
  equivalent?: string[];
  reasoning: string;
};

const FORMATS: Record<AttributeKind, string> = {
  text: "text",
  ico: "IČO (8 digits)",
  dic: "DIČ (CZ and 8 to 10 digits)",
  account: "account number (prefix-number/bank code)",
  id: "identifier",
  amount: "amount",
  year: "year (4 digits)",
};

// The tool runtime has no String.prototype.normalize, so map the letters of
// Czech, Slovak and German names directly.
const PLAIN: Record<string, string> = {
  á: "a", ä: "a", č: "c", ď: "d", é: "e", ě: "e", ë: "e", í: "i", ĺ: "l", ľ: "l", ň: "n", ó: "o", ô: "o", ö: "o",
  ŕ: "r", ř: "r", š: "s", ť: "t", ú: "u", ů: "u", ü: "u", ý: "y", ž: "z", ß: "ss",
};

export function stripDiacritics(value: string): string {
  return value.replace(/[^\x00-\x7f]/g, (c) => {
    const lower = c.toLowerCase();
    const plain = PLAIN[lower];
    if (!plain) return c;
    return lower === c ? plain : plain.toUpperCase();
  });
}

// The value in a comparable form, or null if it doesn't fit its kind's format.
export function normalizeValue(kind: AttributeKind, value: string): string | null {
  const v = value.trim();
  const compact = v.replace(/\s+/g, "");
  switch (kind) {
    case "text": {
      const text = stripDiacritics(v.toLowerCase()).replace(/[^a-z0-9]/g, "");
      return text || null;
    }
    case "ico":
      return /^\d{8}$/.test(compact) ? compact : null;
    case "dic": {
      const dic = compact.toUpperCase();
      return /^CZ\d{8,10}$/.test(dic) ? dic : null;
    }
    case "account": {
      const m = /^(?:(\d{1,6})-)?(\d{2,10})\/(\d{4})$/.exec(compact);
      if (!m) return null;
      const trim = (digits: string) => digits.replace(/^0+(?=\d)/, "");
      return `${m[1] && trim(m[1]) !== "0" ? `${trim(m[1])}-` : ""}${trim(m[2])}/${m[3]}`;
    }
    case "id":
      return compact ? compact.toUpperCase() : null;
    case "amount":
      return normalizeAmount(v);
    case "year":
      return /^(19|20)\d{2}$/.test(compact) ? compact : null;
  }
}

// "1 620 000,00 CZK", "1.620.000,-", "1620000.00" → "1620000.00".
function normalizeAmount(value: string): string | null {
  let s = value.replace(/,-+\s*$/, "").replace(/[^\d,.]/g, "");
  if (!/\d/.test(s)) return null;
  const comma = s.lastIndexOf(",");
  const dot = s.lastIndexOf(".");
  if (comma >= 0 && dot >= 0) {
    const decimal = comma > dot ? "," : ".";
    s = s.split(decimal === "," ? "." : ",").join("").replace(",", ".");
  } else if (comma >= 0) {
    s = /,\d{1,2}$/.test(s) && s.indexOf(",") === comma ? s.replace(",", ".") : s.split(",").join("");
  } else if (dot >= 0 && !(/\.\d{1,2}$/.test(s) && s.indexOf(".") === dot)) {
    s = s.split(".").join("");
  }
  const n = Number(s);
  return Number.isFinite(n) ? n.toFixed(2) : null;
}

type Entry = { source: string; document_id?: string; page?: number; value: string; normalized: string | null };

const where = (e: Entry) => (e.page === undefined ? e.source : `${e.source} p. ${e.page}`);

export function checkConsistency(
  spec: ConsistencySpec,
  run: Run,
  getRead: (documentId: string) => DocumentRead | null,
  input: ConsistencyInput,
): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  const keys = spec.attributes.map((a) => a.key);
  const listed = input.attributes ?? [];
  const valueCount = listed.reduce((n, a) => n + a.values.length, 0);

  if (input.status === "not_applicable") {
    if (!spec.optional) problems.push(`status not_applicable is not allowed: every case has a ${spec.entity}.`);
    if (valueCount) problems.push(`status not_applicable, but you listed values for the ${spec.entity}. Compare them and use passed or conflict.`);
    if (problems.length) return rejected(problems);
    return {
      result: {
        rule_id: spec.rule_id,
        status: "not_applicable",
        expected: `The same ${spec.entity} in every document, if the case has one`,
        found: `No ${spec.entity} in this case`,
        sources: [],
        reasoning: input.reasoning,
      },
    };
  }

  const reference = spec.reference?.(run) ?? null;
  const entries = new Map<string, Entry[]>();
  for (const a of listed) {
    const attributeSpec = spec.attributes.find((s) => s.key === a.attribute);
    if (!attributeSpec) {
      problems.push(`"${a.attribute}" is not an attribute of this rule; the attributes are ${keys.join(", ")}.`);
      continue;
    }
    if (entries.has(a.attribute)) problems.push(`Attribute ${a.attribute} is listed twice.`);
    const list: Entry[] = [];
    const seen = new Set<string>();
    for (const v of a.values) {
      const value = v.value?.trim() ?? "";
      const document = findDocument(run, v.document_id);
      const at = `${a.attribute} in ${document?.title ?? v.document_id}${v.page === undefined ? "" : ` p. ${v.page}`}`;
      if (!value) problems.push(`${at}: give the value, or leave out documents that don't show it.`);
      if (!document) {
        problems.push(`${at}: document_id "${v.document_id}" is not a document of this case.`);
        continue;
      }
      const read = getRead(document.document_id);
      if (!read) problems.push(`${at}: read ${document.title} with get_document first.`);
      if (v.page === undefined) problems.push(`${at}: give the page the value is on.`);
      else if (read && (v.page < 1 || v.page > read.page_count)) problems.push(`${at}: page ${v.page} is not a page of this document (1-${read.page_count}).`);
      else if (read?.empty_pages.includes(v.page)) problems.push(`${at}: page ${v.page} has no text, so the value can't come from it.`);
      const key = `${document.document_id}:${v.page}:${value}`;
      if (seen.has(key)) problems.push(`${at}: listed twice.`);
      seen.add(key);
      list.push({ source: document.title, document_id: document.document_id, page: v.page, value, normalized: normalizeValue(attributeSpec.kind, value) });
    }
    entries.set(a.attribute, list);
  }
  const unlisted = keys.filter((k) => !entries.has(k));
  if (unlisted.length) problems.push(`List every attribute, with an empty values list if no document shows it. Not listed: ${unlisted.join(", ")}.`);
  for (const key of input.equivalent ?? []) {
    const attribute = spec.attributes.find((a) => a.key === key);
    if (!attribute) problems.push(`equivalent: "${key}" is not an attribute of this rule.`);
    else if (attribute.kind !== "text") problems.push(`equivalent: ${key} is an identifier or number; its values must match exactly, so a difference is a conflict.`);
  }
  if (problems.length) return rejected(problems);

  const equivalent = new Set(input.equivalent ?? []);
  const issues: string[] = [];
  // One source per value. The values of a differing attribute are the sides of
  // the conflict (compare_a, compare_b, ...; a is the reference value's side).
  const sources: Source[] = [];
  const compared: string[] = [];
  const attributes = spec.attributes.map((attribute) => {
    const referenceValue = reference?.values[attribute.key]?.trim();
    const all: Entry[] = [
      ...(referenceValue ? [{ source: reference!.source, value: referenceValue, normalized: normalizeValue(attribute.kind, referenceValue) }] : []),
      ...(entries.get(attribute.key) ?? []),
    ];
    const invalid = all.filter((e) => e.normalized === null && e.document_id);
    for (const e of invalid) issues.push(`${attribute.label} "${e.value}" (${where(e)}) is not a valid ${FORMATS[attribute.kind]}`);
    const groups = new Map<string, Entry[]>();
    for (const e of all) if (e.normalized !== null) groups.set(e.normalized, [...(groups.get(e.normalized) ?? []), e]);
    const differs = groups.size > 1;
    const tolerated = differs && attribute.kind === "text" && equivalent.has(attribute.key);
    if (differs && !tolerated) {
      issues.push(`${attribute.label} differs: ${[...groups.values()].map((g) => `${g[0].value} (${g.map(where).join("; ")})`).join(" vs ")}`);
    }
    if (all.length >= 2 || invalid.length) compared.push(attribute.key);
    const sides = [...groups.keys()];
    for (const e of entries.get(attribute.key) ?? []) {
      const side = differs && !tolerated && e.normalized !== null ? sides.indexOf(e.normalized) : -1;
      sources.push({
        document_id: e.document_id!,
        title: e.source,
        page: e.page,
        role: side >= 0 ? `compare_${String.fromCharCode(97 + side)}` : "evidence",
        field: attribute.key,
        ...((side >= 0 || e.normalized === null) && { issue: attribute.label }),
        locate: { value: e.value, ...spec.regions },
      });
    }
    return {
      attribute: attribute.key,
      reference: referenceValue ?? null,
      values: (entries.get(attribute.key) ?? []).map((e) => ({ document_id: e.document_id, page: e.page, value: e.value, valid: e.normalized !== null })),
      consistent: !invalid.length && (!differs || tolerated),
      ...(tolerated && { judged_equivalent: true }),
    };
  });

  const judged = spec.attributes.filter((a) => attributes.find((r) => r.attribute === a.key && r.judged_equivalent));
  if (input.status === "passed") {
    if (issues.length) {
      problems.push(`status passed, but: ${issues.join("; ")}. Use conflict. If text values only differ in how they are written (e.g. address order, abbreviations), list the attribute in equivalent and explain in reasoning.`);
    } else if (!compared.length) {
      problems.push(`status passed, but no attribute has two values to compare. Use cannot_verify${spec.optional ? ", or not_applicable if the case has no " + spec.entity : ""}.`);
    }
  }
  if (input.status === "conflict" && !issues.length) {
    problems.push(`status conflict, but every value matches${judged.length ? ` (you judged ${judged.map((a) => a.key).join(", ")} equivalent)` : ""}. Use passed.`);
  }
  if (input.status === "cannot_verify" && compared.length) {
    problems.push(`status cannot_verify, but there are values to compare for ${compared.join(", ")}. Use passed or conflict; leave out values you can't read reliably.`);
  }
  if (problems.length) return rejected(problems);

  const documents = new Set(sources.map((source) => source.document_id));
  const labels = spec.attributes.map((a) => a.label).join(", ");
  const referenceText = reference
    ? spec.attributes.filter((a) => reference.values[a.key]).map((a) => `${a.label} ${reference.values[a.key]}`).join(", ")
    : "";
  return {
    result: {
      rule_id: spec.rule_id,
      status: input.status,
      expected: reference && referenceText
        ? `${referenceText} (${reference.source}), the same in every document`
        : `The same ${labels} in every document`,
      found: input.status === "cannot_verify"
        ? `Nothing to compare: no ${spec.entity} value appears in two sources`
        : issues.length ? issues.join("; ") : `Consistent across ${documents.size} document${documents.size === 1 ? "" : "s"}${reference && referenceText ? ` and ${reference.source}` : ""}`,
      sources: sources.sort((a, b) => a.title.localeCompare(b.title) || (a.page ?? 0) - (b.page ?? 0)),
      details: { reference: reference && { source: reference.source, values: reference.values }, attributes },
      reasoning: input.reasoning,
    },
  };
}

// What the *_consistent tools take: each distinct value once, with every place
// it appears as "<ref>:<page>" (e.g. "D3:1"). Much shorter than one entry per
// document with its full document_id, which made these calls slow to write.
export type GroupedConsistencyInput = Omit<ConsistencyInput, "attributes"> & {
  attributes?: Array<{ attribute: string; values: Array<{ value: string; at: string[] }> }>;
};

const PLACE = /^\s*(.+?)\s*:\s*(?:p\.?\s*)?(\d+)\s*$/i;

// Expands the places into checkConsistency's input. Problems with places are
// reported together with checkConsistency's own, so one retry can fix them all.
export function checkGroupedConsistency(
  spec: ConsistencySpec,
  run: Run,
  getRead: (documentId: string) => DocumentRead | null,
  input: GroupedConsistencyInput,
): CheckOutcome {
  const problems: string[] = [];
  const attributes = (input.attributes ?? []).map((a) => ({
    attribute: a.attribute,
    values: a.values.flatMap(({ value, at }) => {
      if (!at?.length) problems.push(`${a.attribute} "${value}": give the places it appears in at, as <ref>:<page>, e.g. D3:1.`);
      return (at ?? []).flatMap((place) => {
        const m = PLACE.exec(place);
        if (!m) {
          problems.push(`${a.attribute} "${value}": "${place}" is not a place; write <ref>:<page>, e.g. D3:1.`);
          return [];
        }
        return [{ document_id: m[1], page: Number(m[2]), value }];
      });
    }),
  }));
  const outcome = checkConsistency(spec, run, getRead, { ...input, attributes: input.attributes && attributes });
  if (!problems.length) return outcome;
  return rejected([...problems, ...(outcome.problems ?? [])]);
}
