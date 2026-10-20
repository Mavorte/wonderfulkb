import { beforeEach, describe, expect, it } from "vitest";
import { recordRule } from "./record";
import { type EvalRegion, type Region, anchorSources, compactRegions, locate } from "./regions";
import { checkGroupedConsistency } from "./rules/consistency";
import { SUPPLIER } from "./rules/consistencySpecs";
import { PURCHASE_CONTRACT } from "./rules/contentSpecs";
import { checkContents } from "./rules/contents";
import { checkRequiredDocuments, toTypedRequirements } from "./rules/requiredDocuments";
import { type DocumentRead, RESULTS_TABLE, type Run, type Source, getDocumentRead, saveDocumentRead, saveDocumentRegions, saveRequirements } from "./run";
import { RUN, createTestContext } from "./testContext";

const reasoning = "because";

const AGREEMENT: EvalRegion[] = [
  { region_id: "p1-r05", page: 1, label: "smluvni_strana", party: "supplier", text: "Dodavatel: Epirock s.r.o., IČO 06493399", bbox: [0.1, 0.2, 0.9, 0.22] },
  {
    region_id: "p2-r14", page: 2, label: "povinny_podklad", party: null, refers_to: ["faktura"],
    text: "a) kopie daňového dokladu dodavatele předmětu financování", bbox: [0.1, 0.5, 0.9, 0.53],
  },
];

const ORDER: EvalRegion[] = [
  { region_id: "p1-r03", page: 1, label: "hlavicka", party: null, text: "Epiroc Czech Republic s.r.o.", bbox: [0.1, 0.05, 0.9, 0.07] },
  {
    region_id: "p1-r04", page: 1, label: "smluvni_strana", party: "supplier", text: "IČO / DIČ | 06493394 / CZ06493394", bbox: [0.08, 0.17, 0.56, 0.18],
    lines: [{ bbox: [0.08, 0.17, 0.15, 0.18], start: 0, end: 9 }, { bbox: [0.38, 0.17, 0.56, 0.18], start: 12, end: 33 }],
  },
  { region_id: "p1-r06", page: 1, label: "smluvni_strana", party: "supplier", text: "Epiroc Czech Republic s.r.o., Modřice", bbox: [0.1, 0.2, 0.6, 0.22] },
  { region_id: "p1-r08", page: 1, label: "cena_platba", party: null, text: "Cena celkem bez DPH | 1 620 000,00 Kč", bbox: [0.1, 0.4, 0.9, 0.42] },
  { region_id: "p2-r02", page: 2, label: "podpisovy_blok", party: "supplier", text: "Za dodavatele: razítko a podpis", bbox: [0.5, 0.8, 0.9, 0.85] },
];

const agreement = compactRegions(AGREEMENT);
const order = compactRegions(ORDER);

describe("locate", () => {
  it("narrows a value in a table row to its line", () => {
    expect(locate(order, 1, { value: "06493394" })).toEqual({ region_id: "p1-r04", page: 1, bbox: [0.38, 0.17, 0.56, 0.18], quote: "06493394", anchor: "lines" });
  });

  it("ignores case, diacritics, spacing and a trailing currency", () => {
    expect(locate(order, 1, { value: "1 620 000,00 CZK" })?.region_id).toBe("p1-r08");
    expect(locate(order, 1, { value: "064 93 394" })?.quote).toBe("06493394");
    expect(locate(agreement, 2, { value: "KOPIE DANOVEHO DOKLADU" })?.region_id).toBe("p2-r14");
  });

  it("prefers the region that fits the rule when the value appears in several", () => {
    expect(locate(order, 1, { value: "Epiroc Czech Republic s.r.o." })?.region_id).toBe("p1-r03");
    expect(locate(order, 1, { value: "Epiroc Czech Republic s.r.o.", labels: ["smluvni_strana"], parties: ["supplier"] })?.region_id).toBe("p1-r06");
  });

  it("looks only on the cited page, and not inside a longer number", () => {
    expect(locate(order, 2, { value: "06493394" })).toBeNull();
    expect(locate(order, 1, { value: "6493394" })).toBeNull();
  });

  it("finds a region by its label, party or required document type alone", () => {
    expect(locate(order, undefined, { labels: ["podpisovy_blok"], parties: ["supplier"] })?.region_id).toBe("p2-r02");
    expect(locate(agreement, undefined, { labels: ["povinny_podklad"], refers_to: ["faktura"] })).toMatchObject({ region_id: "p2-r14", page: 2, anchor: "region" });
    expect(locate(agreement, undefined, { labels: ["povinny_podklad"], refers_to: ["ruceni"] })).toBeNull();
  });
});

describe("anchorSources", () => {
  const at = { document_id: "ord", title: "10_Objednavka.pdf", page: 1 };

  it("falls back to the page without regions, and never keeps the hint", () => {
    const [source] = anchorSources([{ ...at, role: "evidence", locate: { value: "06493394" } }], () => null);
    expect(source).toEqual({ ...at, role: "evidence", quote: "06493394", anchor: "page_only" });
  });

  it("leaves sources without a hint as they are and drops duplicates", () => {
    const plain: Source = { ...at };
    const hinted: Source = { ...at, role: "evidence", locate: { value: "06493394" } };
    expect(anchorSources([plain, hinted, hinted], () => order)).toEqual([plain, { ...at, role: "evidence", region_id: "p1-r04", bbox: [0.38, 0.17, 0.56, 0.18], quote: "06493394", anchor: "lines" }]);
  });
});

describe("recorded results carry the regions of each issue", () => {
  const run: Run = { ...RUN, documents: RUN.documents.map((d, i) => ({ ...d, ref: `D${i + 1}` })) };
  const read = (signatures: DocumentRead["signatures"]): DocumentRead => ({ page_count: 2, empty_pages: [], pages_failed: [], confidence: 0.98, signatures });
  let test: ReturnType<typeof createTestContext>;

  beforeEach(() => {
    test = createTestContext();
    test.ctx.kv.set("case_eval_run", run);
    saveDocumentRead(test.ctx, run, "agr", read([]));
    saveDocumentRead(test.ctx, run, "ord", read([{ role: "borrower", page: 2 }]));
    saveDocumentRegions(test.ctx, run, "agr", agreement);
    saveDocumentRegions(test.ctx, run, "ord", order);
  });

  const saved = (ruleId: string) => {
    const row = test.tables[RESULTS_TABLE].find((r) => r.data.rule_id === ruleId)!;
    return { sources: JSON.parse(row.data.sources) as Source[], details: row.data.details && JSON.parse(row.data.details) };
  };

  it("a conflict points at both sides", async () => {
    const reply = await recordRule(test.ctx, (r) =>
      checkGroupedConsistency(SUPPLIER, r, (id) => getDocumentRead(test.ctx, r, id), {
        status: "conflict",
        attributes: [
          { attribute: "name", values: [{ value: "Epirock s.r.o.", at: ["D1:1"] }, { value: "Epiroc Czech Republic s.r.o.", at: ["D2:1"] }] },
          { attribute: "ico", values: [{ value: "06493399", at: ["D1:1"] }, { value: "06493394", at: ["D2:1"] }] },
          { attribute: "dic", values: [] },
          { attribute: "address", values: [] },
          { attribute: "bank_account", values: [] },
        ],
        reasoning,
      }));
    expect(reply).toMatchObject({ accepted: true, status: "conflict" });
    const { sources, details } = saved("supplier_consistent");
    expect(sources.filter((s) => s.issue === "IČO")).toEqual([
      { document_id: "agr", title: "0_Form_Smlouva.pdf", page: 1, role: "compare_a", field: "ico", issue: "IČO", region_id: "p1-r05", bbox: [0.1, 0.2, 0.9, 0.22], quote: "06493399", anchor: "region" },
      { document_id: "ord", title: "10_Podklady_k_vylate_objednavka.pdf", page: 1, role: "compare_b", field: "ico", issue: "IČO", region_id: "p1-r04", bbox: [0.38, 0.17, 0.56, 0.18], quote: "06493394", anchor: "lines" },
    ]);
    expect(sources.find((s) => s.issue === "name" && s.document_id === "ord")?.region_id).toBe("p1-r06");
    expect(sources.every((s) => !("locate" in s))).toBe(true);
    expect(details.attributes[1].values.map((v: { document_id: string }) => v.document_id)).toEqual(["agr", "ord"]);
  });

  it("rejects places that aren't <ref>:<page>, all at once", async () => {
    const reply = await recordRule(test.ctx, (r) =>
      checkGroupedConsistency(SUPPLIER, r, (id) => getDocumentRead(test.ctx, r, id), {
        status: "passed",
        attributes: [{ attribute: "ico", values: [{ value: "06493399", at: ["D1"] }, { value: "06493394", at: [] }] }],
        reasoning,
      }));
    expect(reply.accepted).toBe(false);
    expect(reply.problems?.slice(0, 2)).toEqual([
      'ico "06493399": "D1" is not a place; write <ref>:<page>, e.g. D3:1.',
      'ico "06493394": give the places it appears in at, as <ref>:<page>, e.g. D3:1.',
    ]);
  });

  it("a missing document points at the agreement's clause requiring it", async () => {
    await recordRule(test.ctx, (r) =>
      checkRequiredDocuments(r, {
        status: "missing",
        requirements: [
          { description: "faktura (daňový doklad)", type: "invoice" },
          { description: "objednávka", type: "purchase_contract", document_id: "D2" },
        ],
        reasoning,
      }), (r, result) => saveRequirements(test.ctx, r, toTypedRequirements(result.details)));
    const { sources, details } = saved("required_documents_present");
    expect(sources).toEqual([
      { document_id: "ord", title: "10_Podklady_k_vylate_objednavka.pdf" },
      {
        document_id: "agr", title: "0_Form_Smlouva.pdf", role: "declaration", issue: "faktura (daňový doklad)",
        page: 2, region_id: "p2-r14", bbox: [0.1, 0.5, 0.9, 0.53], quote: "a) kopie daňového dokladu dodavatele předmětu financování", anchor: "region",
      },
    ]);
    expect(details[1].document_id).toBe("ord");
  });

  it("a missing signature points at the party's signature block", async () => {
    saveRequirements(test.ctx, run, [{ type: "purchase_contract", document_id: "ord" }]);
    const fields = [
      { field: "buyer", value: "SOLOM Rec s.r.o.", page: 1 },
      { field: "seller", value: "Epiroc Czech Republic s.r.o.", page: 1 },
      { field: "subject", value: "Epiroc CC 3100", page: 1 },
      { field: "price", value: "1 620 000,00 Kč", page: 1 },
    ];
    const reply = await recordRule(test.ctx, (r) =>
      checkContents(PURCHASE_CONTRACT, r, [{ type: "purchase_contract", document_id: "ord" }], getDocumentRead(test.ctx, r, "D2"), { status: "missing", document_id: "D2", fields, reasoning }));
    expect(reply).toMatchObject({ accepted: true, status: "missing" });
    const { sources } = saved("purchase_contract_contents");
    expect(sources.find((s) => s.role === "missing_value")).toMatchObject({ document_id: "ord", issue: "seller (signature or confirmation) signature", region_id: "p2-r02", page: 2 });
    expect(sources.find((s) => s.field === "price")).toMatchObject({ role: "evidence", region_id: "p1-r08", quote: "1 620 000,00 Kč" });
    expect(sources.find((s) => s.field === "seller")?.region_id).toBe("p1-r06");
    expect(sources.filter((s) => s.field).map((s) => [s.field, s.anchor])).toEqual([["buyer", "page_only"], ["seller", "region"], ["subject", "page_only"], ["price", "region"]]);
  });
});

// Regions are compact in KV: lines as [x0, y0, x1, y1, start, end], dropped for one line.
it("compacts regions for KV", () => {
  const [single, table] = [compactRegions([ORDER[0]])[0], compactRegions([ORDER[1]])[0]] as Region[];
  expect(single).toEqual({ id: "p1-r03", page: 1, label: "hlavicka", party: null, text: ORDER[0].text, bbox: ORDER[0].bbox, lines: [] });
  expect(table.lines).toEqual([[0.08, 0.17, 0.15, 0.18, 0, 9], [0.38, 0.17, 0.56, 0.18, 12, 33]]);
});
