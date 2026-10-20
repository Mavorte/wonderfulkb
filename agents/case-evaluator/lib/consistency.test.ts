import { describe, expect, it } from "vitest";
import { checkClientStatus, normalizePerson } from "./rules/clientStatus";
import { type ConsistencyInput, checkConsistency, normalizeValue } from "./rules/consistency";
import { CONTRACT_NUMBER, GUARANTOR, PROVIDER, RECIPIENT, SUPPLIER } from "./rules/consistencySpecs";
import type { DocumentRead } from "./run";
import { RUN } from "./testContext";

const reasoning = "because";

const run = { ...RUN, documents: [...RUN.documents, { document_id: "pay", title: "09_Form_Dohoda.pdf", label: "dohoda_o_zaplaceni_kupni_ceny" }] };

const READ: DocumentRead = { page_count: 4, empty_pages: [4], pages_failed: [], confidence: 0.98, signatures: [] };
const readAll = () => READ;

const check = (spec: Parameters<typeof checkConsistency>[0], input: Partial<ConsistencyInput>, getRead: (id: string) => DocumentRead | null = readAll) =>
  checkConsistency(spec, run, getRead, { status: "passed", reasoning, ...input });

const supplier = (ico2: string, extra: Partial<ConsistencyInput> = {}) =>
  check(SUPPLIER, {
    attributes: [
      { attribute: "name", values: [{ document_id: "agr", page: 1, value: "Epirock s.r.o." }, { document_id: "ord", page: 1, value: "Epiroc Czech Republic s.r.o." }] },
      { attribute: "ico", values: [{ document_id: "agr", page: 1, value: "06493399" }, { document_id: "ord", page: 1, value: ico2 }] },
      { attribute: "dic", values: [] },
      { attribute: "address", values: [] },
      { attribute: "bank_account", values: [] },
    ],
    ...extra,
  });

describe("normalizeValue", () => {
  it("normalizes each kind and rejects malformed identifiers", () => {
    expect(normalizeValue("ico", "046 06 812")).toBe("04606812");
    expect(normalizeValue("ico", "YYYYYYY")).toBeNull();
    expect(normalizeValue("ico", "2531788")).toBeNull();
    expect(normalizeValue("dic", "cz 04606812")).toBe("CZ04606812");
    expect(normalizeValue("dic", "XXXXXXX")).toBeNull();
    expect(normalizeValue("account", "0162710187/0100")).toBe(normalizeValue("account", "162710187 / 0100"));
    expect(normalizeValue("account", "115-2001130287/0100")).toBe("115-2001130287/0100");
    expect(normalizeValue("text", "Třinec - Lyžbice")).toBe("trineclyzbice");
    expect(normalizeValue("text", "ŽLUŤOUČKÝ kůň Ďáblův")).toBe("zlutouckykundabluv");
    expect(normalizeValue("id", "170170 /25")).toBe("170170/25");
  });

  it("parses Czech and English amounts", () => {
    for (const v of ["1 620 000,00 CZK", "1.620.000,-", "1620000.00", "1,620,000.00", "1 620 000 Kč"]) expect(normalizeValue("amount", v)).toBe("1620000.00");
    expect(normalizeValue("amount", "340 200,5")).toBe("340200.50");
    expect(normalizeValue("amount", "n/a")).toBeNull();
  });
});

describe("checkConsistency", () => {
  it("records a supplier IČO conflict and rejects passed for it", () => {
    expect(supplier("06493394", { status: "passed", equivalent: ["name"] }).problems?.[0]).toMatch(/IČO differs: 06493399 \(0_Form_Smlouva.pdf p. 1\) vs 06493394/);
    const { result } = supplier("06493394", { status: "conflict" });
    expect(result?.found).toMatch(/^name differs: .*; IČO differs/);
    expect([...new Set(result?.sources.map((s) => s.title))]).toEqual(["0_Form_Smlouva.pdf", "10_Podklady_k_vylate_objednavka.pdf"]);
    const ico = result?.sources.filter((s) => s.issue === "IČO").map(({ document_id, role, locate }) => [document_id, role, locate?.value]);
    expect(ico).toEqual([["agr", "compare_a", "06493399"], ["ord", "compare_b", "06493394"]]);
  });

  it("lets the agent judge differing text equivalent, but never an identifier", () => {
    expect(supplier("06493399", { status: "passed", equivalent: ["name"] }).result?.found).toBe("Consistent across 2 documents");
    expect(supplier("06493399", { status: "conflict", equivalent: ["name"] }).problems?.[0]).toMatch(/every value matches \(you judged name equivalent\)/);
    expect(supplier("06493399", { status: "passed", equivalent: ["ico" as never] }).problems?.[0]).toMatch(/must match exactly/);
  });

  it("compares against the reference and flags malformed values", () => {
    const attributes = (ico: string) => [
      { attribute: "name", values: [{ document_id: "agr", page: 1, value: "SOLOM Rec s. r. o." }] },
      { attribute: "ico", values: [{ document_id: "agr", page: 1, value: ico }] },
      { attribute: "dic", values: [] },
      { attribute: "address", values: [] },
    ];
    expect(check(RECIPIENT, { attributes: attributes("04606812") }).result).toMatchObject({
      status: "passed",
      found: "Consistent across 1 document and the client record",
      expected: "name SOLOM Rec s.r.o., IČO 04606812, DIČ CZ04606812, address (sídlo) nám. Svobody 527, 739 61 Třinec - Lyžbice (the client record), the same in every document",
    });
    expect(check(RECIPIENT, { attributes: attributes("YYYYYYY") }).problems?.[0]).toMatch(/IČO "YYYYYYY" \(0_Form_Smlouva.pdf p. 1\) is not a valid IČO/);
  });

  it("flags the provider's name, DIČ and account against the other documents", () => {
    const { result } = check(PROVIDER, {
      status: "conflict",
      attributes: [
        { attribute: "name", values: [{ document_id: "agr", page: 1, value: "SGX Finance Czech Republic s.r.o." }, { document_id: "pay", page: 1, value: "SG Equipment Finance Czech Republic s.r.o." }] },
        { attribute: "ico", values: [{ document_id: "agr", page: 1, value: "61061344" }, { document_id: "pay", page: 1, value: "61061344" }] },
        { attribute: "dic", values: [{ document_id: "agr", page: 1, value: "XXXXXXX" }, { document_id: "pay", page: 1, value: "CZ61061344" }] },
        { attribute: "bank_account", values: [{ document_id: "agr", page: 1, value: "0162710187/0000" }, { document_id: "pay", page: 1, value: "0162710187/0100" }] },
      ],
    });
    expect(result?.found).toBe(
      "name differs: SGX Finance Czech Republic s.r.o. (0_Form_Smlouva.pdf p. 1) vs SG Equipment Finance Czech Republic s.r.o. (09_Form_Dohoda.pdf p. 1); DIČ \"XXXXXXX\" (0_Form_Smlouva.pdf p. 1) is not a valid DIČ (CZ and 8 to 10 digits); bank account differs: 0162710187/0000 (0_Form_Smlouva.pdf p. 1) vs 0162710187/0100 (09_Form_Dohoda.pdf p. 1)",
    );
  });

  it("passes a provider that is the same in every document, whoever it is", () => {
    const { result } = check(PROVIDER, {
      attributes: [
        { attribute: "name", values: [{ document_id: "agr", page: 1, value: "Nerovex Finance s.r.o." }, { document_id: "pay", page: 1, value: "Nerovex Finance s.r.o." }] },
        { attribute: "ico", values: [{ document_id: "agr", page: 1, value: "98000110" }, { document_id: "pay", page: 1, value: "98000110" }] },
        { attribute: "dic", values: [{ document_id: "agr", page: 1, value: "CZ98000110" }] },
        { attribute: "bank_account", values: [{ document_id: "agr", page: 1, value: "7000001507/9999" }, { document_id: "pay", page: 1, value: "7000001507/9999" }] },
      ],
    });
    expect(result).toMatchObject({ status: "passed", found: "Consistent across 2 documents" });
  });

  it("flags a second loan number, even within one document", () => {
    const values = [
      { document_id: "agr", page: 1, value: "170170/25" },
      { document_id: "pay", page: 1, value: "17023644/25" },
    ];
    expect(check(CONTRACT_NUMBER, { attributes: [{ attribute: "loan_number", values }] }).problems?.[0]).toMatch(
      /loan contract number differs: 170170\/25 \(the case record; 0_Form_Smlouva.pdf p. 1\) vs 17023644\/25 \(09_Form_Dohoda.pdf p. 1\)/,
    );
  });

  it("checks documents, pages and that every attribute is listed", () => {
    const problems = check(CONTRACT_NUMBER, {
      attributes: [{ attribute: "loan_number", values: [{ document_id: "x", page: 1, value: "1" }, { document_id: "agr", page: 4, value: "1" }, { document_id: "ord", page: 1, value: "1" }] }],
    }, (id) => (id === "ord" ? null : READ)).problems;
    expect(problems).toEqual([
      'loan_number in x p. 1: document_id "x" is not a document of this case.',
      "loan_number in 0_Form_Smlouva.pdf p. 4: page 4 has no text, so the value can't come from it.",
      "loan_number in 10_Podklady_k_vylate_objednavka.pdf p. 1: read 10_Podklady_k_vylate_objednavka.pdf with get_document first.",
    ]);
    expect(check(GUARANTOR, { attributes: [] }).problems?.[0]).toMatch(/Not listed: name, ico, address/);
  });

  it("allows not_applicable only for an optional entity without values, and cannot_verify only with nothing to compare", () => {
    expect(check(GUARANTOR, { status: "not_applicable" }).result?.found).toBe("No guarantor (ručitel) in this case");
    expect(check(SUPPLIER, { status: "not_applicable" }).problems?.[0]).toMatch(/every case has a supplier/);
    const single = [{ attribute: "loan_number", values: [{ document_id: "agr", page: 1, value: "170170/25" }] }];
    expect(check(CONTRACT_NUMBER, { status: "cannot_verify", attributes: single }).problems?.[0]).toMatch(/values to compare for loan_number/);
    const empty = GUARANTOR.attributes.map((a) => ({ attribute: a.key, values: [] }));
    expect(check(GUARANTOR, { status: "passed", attributes: empty }).problems?.[0]).toMatch(/no attribute has two values/);
    expect(check(GUARANTOR, { status: "cannot_verify", attributes: empty }).result?.status).toBe("cannot_verify");
  });
});

describe("checkClientStatus", () => {
  const signedBy = (name: string) => [{ name, document_id: "agr", page: 3 }];

  it("passes an authorized signatory, ignoring titles, diacritics and order", () => {
    expect(normalizePerson("Ing. Jiří Labuda")).toBe(normalizePerson("LABUDA Jiri"));
    const { result } = checkClientStatus(run, readAll, { status: "passed", signatories: signedBy("Ing. Jiří Labuda"), reasoning });
    expect(result).toMatchObject({ status: "passed", found: "Active, KYC ok, signed by Ing. Jiří Labuda", expected: "Active client with KYC ok; signed by Jiří Labuda (client record)" });
  });

  it("records an unauthorized signatory as a conflict and rejects passed for it", () => {
    expect(checkClientStatus(run, readAll, { status: "passed", signatories: signedBy("Petr Fiala"), reasoning }).problems?.[0]).toMatch(/Petr Fiala signs for the recipient but is not an authorized signatory/);
    expect(checkClientStatus(run, readAll, { status: "conflict", signatories: signedBy("Petr Fiala"), reasoning }).result?.status).toBe("conflict");
  });

  it("counts a signatory without an authorized flag as authorized, as the live client API sends them", () => {
    const live = { ...run, client: { ...run.client!, signatories: [{ name: "Matěj Vřesník", function: "jednatel" }] } };
    expect(checkClientStatus(live, readAll, { status: "passed", signatories: signedBy("Matěj Vřesník"), reasoning }).result?.status).toBe("passed");
    const revoked = { ...run, client: { ...run.client!, signatories: [{ name: "Matěj Vřesník", authorized: false }] } };
    expect(checkClientStatus(revoked, readAll, { status: "conflict", signatories: signedBy("Matěj Vřesník"), reasoning }).result?.status).toBe("conflict");
  });

  it("flags inactive clients and KYC from the client record", () => {
    const blocked = { ...run, client: { ...run.client!, status: "blocked", kyc: { status: "expired" } } };
    const { result } = checkClientStatus(blocked, readAll, { status: "conflict", signatories: signedBy("Jiří Labuda"), reasoning });
    expect(result?.found).toBe('client status is "blocked", not active; KYC status is "expired", not ok');
  });

  it("allows cannot_verify without a client record or signatories, and rejects conflict when all is well", () => {
    expect(checkClientStatus({ ...run, client: null }, readAll, { status: "cannot_verify", signatories: [], reasoning }).result?.found).toBe("No client record");
    expect(checkClientStatus(run, readAll, { status: "cannot_verify", signatories: [], reasoning }).result?.status).toBe("cannot_verify");
    expect(checkClientStatus(run, readAll, { status: "conflict", signatories: signedBy("Jiří Labuda"), reasoning }).problems).toHaveLength(1);
  });
});
