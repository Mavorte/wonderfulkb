import { describe, expect, it } from "vitest";
import { getVerdict } from "./rules";
import { checkLoanAgreement } from "./rules/loanAgreement";
import { checkRecipientMatch, normalizeName } from "./rules/recipientMatch";
import { checkRequiredDocuments } from "./rules/requiredDocuments";
import { RUN } from "./testContext";

const reasoning = "because";

describe("checkLoanAgreement", () => {
  it("accepts passed with a case document", () => {
    const { result } = checkLoanAgreement(RUN, { status: "passed", document_id: "agr", reasoning });
    expect(result).toMatchObject({ status: "passed", found: "0_Form_Smlouva.pdf", sources: [{ document_id: "agr" }] });
  });

  it("rejects an unknown document, passed without a document, and missing with one", () => {
    expect(checkLoanAgreement(RUN, { status: "passed", document_id: "x", reasoning }).problems).toHaveLength(1);
    expect(checkLoanAgreement(RUN, { status: "passed", reasoning }).problems).toHaveLength(1);
    expect(checkLoanAgreement(RUN, { status: "missing", document_id: "agr", reasoning }).problems).toHaveLength(1);
  });

  it("requires reasoning", () => {
    expect(checkLoanAgreement(RUN, { status: "missing", reasoning: " " }).problems?.[0]).toMatch(/reasoning/);
  });
});

describe("checkRequiredDocuments", () => {
  const a = { description: "daňový doklad", type: "invoice" as const };
  const b = { description: "objednávka", type: "purchase_contract" as const, document_id: "ord" };

  it("records missing with the unmatched items and the mapping", () => {
    const { result } = checkRequiredDocuments(RUN, { status: "missing", requirements: [a, b], reasoning });
    expect(result?.found).toBe("No document for: daňový doklad");
    expect(result?.details).toEqual([
      { description: "daňový doklad", type: "invoice", document_id: null, title: null },
      { description: "objednávka", type: "purchase_contract", document_id: "ord", title: "10_Podklady_k_vylate_objednavka.pdf" },
    ]);
  });

  it("rejects a status that the mapping contradicts", () => {
    expect(checkRequiredDocuments(RUN, { status: "passed", requirements: [a, b], reasoning }).problems?.[0]).toMatch(/no document: daňový doklad/);
    expect(checkRequiredDocuments(RUN, { status: "missing", requirements: [b], reasoning }).problems?.[0]).toMatch(/every requirement/);
    expect(checkRequiredDocuments(RUN, { status: "cannot_verify", requirements: [b], reasoning }).problems).toHaveLength(1);
    expect(checkRequiredDocuments(RUN, { status: "passed", requirements: [], reasoning }).problems).toHaveLength(1);
  });

  it("rejects unknown documents and duplicate items", () => {
    const problems = checkRequiredDocuments(RUN, { status: "passed", requirements: [{ ...b, document_id: "x" }, b], reasoning }).problems;
    expect(problems?.join("\n")).toMatch(/"x" is not a document/);
    expect(problems?.join("\n")).toMatch(/listed twice/);
  });

  it("rejects an unknown document type", () => {
    const problems = checkRequiredDocuments(RUN, { status: "passed", requirements: [{ ...b, type: "letter" as never }], reasoning }).problems;
    expect(problems?.[0]).toMatch(/type must be one of/);
  });
});

describe("checkRecipientMatch", () => {
  const base = { document_id: "agr", page: 1, reasoning };

  it("passes matching values, ignoring legal-form punctuation", () => {
    expect(normalizeName("SOLOM Rec s. r. o.")).toBe(normalizeName("SOLOM Rec s.r.o."));
    const { result } = checkRecipientMatch(RUN, { ...base, status: "passed", agreement_name: "SOLOM Rec s. r. o.", agreement_ico: "046 06 812" });
    expect(result).toMatchObject({ status: "passed", expected: "SOLOM Rec s.r.o., IČO 04606812" });
  });

  it("records a placeholder IČO as a conflict and rejects passed for it", () => {
    const input = { ...base, agreement_name: "SOLOM Rec s.r.o.", agreement_ico: "YYYYYYY" };
    expect(checkRecipientMatch(RUN, { ...input, status: "conflict" }).result?.found).toBe("SOLOM Rec s.r.o., IČO YYYYYYY");
    expect(checkRecipientMatch(RUN, { ...input, status: "passed" }).problems?.[0]).toMatch(/IČO "YYYYYYY" vs client "04606812"/);
  });

  it("rejects conflict for matching values and cannot_verify when everything is there", () => {
    const input = { ...base, agreement_name: "SOLOM Rec s.r.o.", agreement_ico: "04606812" };
    expect(checkRecipientMatch(RUN, { ...input, status: "conflict" }).problems).toHaveLength(1);
    expect(checkRecipientMatch(RUN, { ...input, status: "cannot_verify" }).problems).toHaveLength(1);
  });

  it("allows cannot_verify without a client record", () => {
    const run = { ...RUN, client: null };
    expect(checkRecipientMatch(run, { ...base, status: "cannot_verify", agreement_name: "X", agreement_ico: "1" }).result?.status).toBe("cannot_verify");
    expect(checkRecipientMatch(run, { ...base, status: "passed", agreement_name: "X", agreement_ico: "1" }).problems?.[0]).toMatch(/no client record/);
  });
});

describe("getVerdict", () => {
  it("ranks missing/conflict over cannot_verify over passed", () => {
    expect(getVerdict(["passed", "passed"])).toBe("ready");
    expect(getVerdict(["passed", "cannot_verify"])).toBe("needs_review");
    expect(getVerdict(["cannot_verify", "conflict"])).toBe("needs_correction");
    expect(getVerdict(["passed", "not_applicable"])).toBe("ready");
  });
});
