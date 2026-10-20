// Document regions (labelled paragraphs and table rows with their position, from
// the AWS documents API via agent-functions/eval-document-regions) and how a
// result's sources are anchored to them. The agent never names regions: it cites
// a value with its document and page, and the tool finds the region, and the
// line within it, that shows the value. A source that can't be placed stays at
// page level (anchor page_only).

import type { DocumentType } from "./rules";
import { stripDiacritics } from "./rules/consistency";
import type { SignatureRole } from "./rules/contents";
import type { Locate, Source } from "./run";

// Region as eval-document-regions returns it.
export type EvalRegion = {
  region_id: string;
  page: number;
  label: string | null;
  party: string | null;
  refers_to?: string[];
  text: string;
  bbox: number[] | null;
  lines?: Array<{ bbox: number[]; start: number; end: number }>;
};

// Compact form kept in KV per document. lines: [x0, y0, x1, y1, start, end],
// start/end being offsets into text; empty for a single-line region.
export type Region = {
  id: string;
  page: number;
  label: string | null;
  party: string | null;
  refers_to?: string[];
  text: string;
  bbox: number[] | null;
  lines: number[][];
};

export type RegionHit = { region_id: string; page: number; bbox?: number[]; quote: string; anchor: "region" | "lines" };

export function compactRegions(regions: EvalRegion[]): Region[] {
  return regions.map((r) => ({
    id: r.region_id,
    page: r.page,
    label: r.label,
    party: r.party,
    ...(r.refers_to?.length && { refers_to: r.refers_to }),
    text: r.text,
    bbox: r.bbox,
    lines: (r.lines ?? []).map((l) => [...l.bbox, l.start, l.end]),
  }));
}

// Lowercase letters and digits only, without diacritics, with the index in the
// original text of each kept character.
function fold(text: string): { folded: string; at: number[] } {
  let folded = "";
  const at: number[] = [];
  for (let i = 0; i < text.length; i++) {
    for (const c of stripDiacritics(text[i].toLowerCase())) {
      if (/[a-z0-9]/.test(c)) {
        folded += c;
        at.push(i);
      }
    }
  }
  return { folded, at };
}

// What to search for: the folded value, then the value without leading and
// trailing letters ("1 620 000,00 CZK" also finds "1 620 000,00 Kč").
function needles(value: string): string[] {
  const full = fold(value).folded;
  const trimmed = full.replace(/^[a-z]+|[a-z]+$/g, "");
  return [full, ...(trimmed !== full && trimmed.length >= 4 ? [trimmed] : [])].filter((n) => n.length >= 3);
}

// Index of needle in folded, not starting inside a longer number.
function findIn(folded: string, needle: string): number {
  for (let i = folded.indexOf(needle); i >= 0; i = folded.indexOf(needle, i + 1)) {
    if (!/\d/.test(needle[0]) || i === 0 || !/\d/.test(folded[i - 1])) return i;
  }
  return -1;
}

const overlaps = (a: string[] | undefined, b: string[] | undefined) => !!a && !!b && a.some((x) => b.includes(x));

function score(region: Region, q: Locate): number {
  return (overlaps(region.refers_to, q.refers_to) ? 4 : 0) + (region.label && q.labels?.includes(region.label) ? 2 : 0) + (region.party && q.parties?.includes(region.party) ? 1 : 0);
}

function fits(region: Region, q: Locate): boolean {
  if (q.labels && !(region.label && q.labels.includes(region.label))) return false;
  if (q.parties && !(region.party && q.parties.includes(region.party))) return false;
  if (q.refers_to && !overlaps(region.refers_to, q.refers_to)) return false;
  return true;
}

// The region on the page (any page when none is given) that shows q.value,
// preferring regions that fit the hint. Without a value, the first region in
// reading order that fits the hint.
export function locate(regions: Region[], page: number | undefined, q: Locate): RegionHit | null {
  const candidates = page === undefined ? regions : regions.filter((r) => r.page === page);
  if (!q.value) {
    if (!q.labels && !q.parties && !q.refers_to) return null;
    const region = candidates.find((r) => fits(r, q));
    return region ? { region_id: region.id, page: region.page, ...(region.bbox && { bbox: region.bbox }), quote: region.text.slice(0, 160), anchor: "region" } : null;
  }
  for (const needle of needles(q.value)) {
    const hits = candidates
      .map((region, order) => {
        const { folded, at } = fold(region.text);
        const i = findIn(folded, needle);
        return i < 0 ? null : { region, order, start: at[i], end: at[i + needle.length - 1] + 1 };
      })
      .filter((h) => h !== null)
      .sort((a, b) => score(b.region, q) - score(a.region, q) || a.region.text.length - b.region.text.length || a.order - b.order);
    const hit = hits[0];
    if (!hit) continue;
    const { region, start, end } = hit;
    const lines = region.lines.filter((l) => l[4] < end && l[5] > start);
    const narrowed = lines.length > 0 && lines.length < region.lines.length;
    const bbox = narrowed
      ? [Math.min(...lines.map((l) => l[0])), Math.min(...lines.map((l) => l[1])), Math.max(...lines.map((l) => l[2])), Math.max(...lines.map((l) => l[3]))]
      : region.bbox;
    return { region_id: region.id, page: region.page, ...(bbox && { bbox }), quote: region.text.slice(start, end), anchor: narrowed ? "lines" : "region" };
  }
  return null;
}

// Replaces each source's locate hint with the region it points at, or marks it
// page_only. Sources without a hint pass through unchanged.
export function anchorSources(sources: Source[], getRegions: (documentId: string) => Region[] | null): Source[] {
  const anchored = sources.map(({ locate: q, ...source }): Source => {
    if (!q) return source;
    const regions = getRegions(source.document_id);
    const hit = regions ? locate(regions, source.page, q) : null;
    if (!hit) return { ...source, ...(q.value && { quote: q.value }), anchor: "page_only" };
    return { ...source, ...hit };
  });
  const seen = new Set<string>();
  return anchored.filter((s) => {
    const key = JSON.stringify([s.document_id, s.page, s.region_id, s.quote, s.role, s.field, s.issue]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// Region labels and parties of the AWS taxonomy
// (be-validator-agent/regions/region_pipeline/labels.yaml) that fit our rules.

const BORROWER = ["borrower", "buyer"];

export const SIGNATURE_PARTIES: Record<SignatureRole, string[]> = {
  provider: ["provider"],
  borrower: BORROWER,
  supplier: ["supplier"],
  guarantor: ["guarantor"],
  insurer: ["insurer"],
};

const party = (...parties: string[]): Locate => ({ labels: ["smluvni_strana"], parties });
const label = (...labels: string[]): Locate => ({ labels });

// Per *_contents field key (contentSpecs.ts). Fields naming a party also locate
// the party's block when their value is missing.
export const FIELD_REGIONS: Record<string, Locate> = {
  issuer: party("supplier"),
  seller: party("supplier"),
  handed_over_by: party("supplier"),
  customer: party(...BORROWER),
  buyer: party(...BORROWER),
  received_by: party(...BORROWER),
  debtor: party(...BORROWER),
  policyholder: party(...BORROWER),
  creditor: party("provider"),
  beneficiary: party("provider"),
  guarantor: party("guarantor"),
  insurer: party("insurer"),
  price: label("cena_platba"),
  vat: label("cena_platba"),
  amount: label("cena_platba"),
  asset_value: label("cena_platba"),
  insured_amount: label("cena_platba"),
  payer_account: label("cena_platba"),
  payee_account: label("cena_platba"),
  payment_details: label("cena_platba"),
  currency: label("cena_platba"),
  subject: label("predmet"),
  asset: label("predmet", "predani"),
  product: label("predmet"),
  model: label("predmet"),
  manufacturer: label("predmet"),
  serial_number: label("predmet"),
  insured_asset: label("predmet"),
  parameters: label("predmet"),
  condition: label("predani"),
  issue_date: label("termin_misto"),
  supply_date: label("termin_misto"),
  due_date: label("termin_misto"),
  handover_date: label("termin_misto", "predani"),
  date: label("termin_misto"),
  insurer_date: label("termin_misto"),
  number: label("hlavicka"),
  policy_number: label("hlavicka"),
  secured_contract: label("odkaz_na_dokument", "zajisteni"),
  reference: label("odkaz_na_dokument"),
  scope: label("zajisteni"),
  commitment: label("zajisteni"),
  transfer_terms: label("zajisteni"),
  benefit_clause: label("zajisteni"),
};

// Document labels (classify/taxonomy.yaml) that a povinny_podklad region's
// refers_to uses for each of our requirement types.
export const REQUIRED_REFERS_TO: Partial<Record<DocumentType, string[]>> = {
  invoice: ["faktura"],
  purchase_contract: ["objednavka"],
  handover_protocol: ["predavaci_protokol"],
  technical_specification: ["technicka_specifikace"],
  payment_proof: ["uhrada_kupni_ceny"],
  security_transfer: ["zajistovaci_prevod_vlastnickeho_prava"],
  insurance_vinculation: ["vinkulace_pojisteni"],
  guarantee: ["ruceni"],
};
