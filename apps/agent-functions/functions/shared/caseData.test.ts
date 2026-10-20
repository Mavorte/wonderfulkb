import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { getCase, getDocument, getRegions, getSignatures, listDocuments } from "./caseData.ts";

function createContext(data: Record<string, unknown>, globals: Record<string, string> = {}) {
  let status = 200;
  return {
    data,
    getStatus: () => status,
    response: { setStatus(value: number) { status = value; } },
    globals: { get: (name: string) => globals[name] },
  };
}

const LIVE = {
  case_eval_documents_api_url: "https://api.example.test/v1",
};

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function stubFetch(routes: Record<string, { status: number; body: unknown }>) {
  const calls: Array<{ url: string; secretName?: string }> = [];
  globalThis.fetch = (async (url: string, init: { secretName?: string }) => {
    calls.push({ url, secretName: init.secretName });
    const route = routes[url] ?? { status: 404, body: { error: "not found" } };
    return new Response(JSON.stringify(route.body), { status: route.status });
  }) as typeof fetch;
  return calls;
}

test("serves a fixture case and its client from the mock layer", async () => {
  const result = await getCase(createContext({ case_id: "mock-solom-rec" }, LIVE));
  assert.ok(!("error" in result));
  assert.equal(result.is_mock, true);
  assert.equal(result.case.metadata?.loan_number, "170170/25");
  assert.equal(result.client?.ico, "04606812");
});

test("an unknown case in mock mode is not found", async () => {
  const context = createContext({ case_id: "case-x" }, { ...LIVE, case_eval_aws_mock: "true" });
  assert.deepEqual(await getCase(context), { error: "case_not_found" });
  assert.equal(context.getStatus(), 404);
});

test("missing API URLs mean mock", async () => {
  const context = createContext({ case_id: "case-x" });
  assert.deepEqual(await getCase(context), { error: "case_not_found" });
});

test("live mode calls the case API with its secret and finds the client by paging", async () => {
  const calls = stubFetch({
    "https://api.example.test/v1/cases/case-1": { status: 200, body: { case_id: "case-1", client_id: "c2", status: "open", created_at: "2026-10-19T09:00:00Z" } },
    "https://api.example.test/v1/clients": { status: 200, body: { clients: [{ client_id: "c1", ico: "1", name: "A", status: "active" }], next_token: "t2" } },
    "https://api.example.test/v1/clients?next_token=t2": { status: 200, body: { clients: [{ client_id: "c2", ico: "12345678", name: "B", status: "active", contacts: [{ email: "x@y" }] }], next_token: null } },
  });
  const result = await getCase(createContext({ case_id: "case-1" }, LIVE));
  assert.ok(!("error" in result));
  assert.equal(result.is_mock, false);
  assert.deepEqual(result.client, { client_id: "c2", name: "B", ico: "12345678", dic: undefined, legal_form: undefined, address: undefined, status: "active", signatories: undefined, kyc: undefined });
  assert.ok(calls.every((c) => c.secretName === "kb-aws-ingest-api-key"));
});

test("a live upstream failure is reported as 502", async () => {
  stubFetch({ "https://api.example.test/v1/cases/case-1": { status: 500, body: {} } });
  const context = createContext({ case_id: "case-1" }, LIVE);
  const result = await getCase(context);
  assert.equal("error" in result && result.error, "upstream");
  assert.equal(context.getStatus(), 502);
});

test("lists fixture documents without their text", async () => {
  const result = await listDocuments(createContext({ case_id: "mock-unhappy" }));
  assert.ok(!("error" in result));
  assert.equal(result.documents.length, 8);
  assert.ok(result.documents.some((d) => d.label === "smlouva_o_uveru"));
  assert.ok(result.documents.every((d) => !("text" in d)));
});

test("live document list uses the documents API secret and follows pages", async () => {
  const doc = (id: string) => ({ document_id: id, title: `${id}.pdf`, label: "x", processing_status: "completed", page_count: 1 });
  const calls = stubFetch({
    "https://api.example.test/v1/cases/case-1/documents": { status: 200, body: { documents: [doc("a")], next_token: "n" } },
    "https://api.example.test/v1/cases/case-1/documents?next_token=n": { status: 200, body: { documents: [doc("b")], next_token: null } },
  });
  const result = await listDocuments(createContext({ case_id: "case-1" }, LIVE));
  assert.ok(!("error" in result));
  assert.deepEqual(result.documents.map((d) => d.document_id), ["a", "b"]);
  assert.ok(calls.every((c) => c.secretName === "kb-aws-ingest-api-key"));
});

test("splits a document's text into numbered pages", async () => {
  const list = await listDocuments(createContext({ case_id: "mock-unhappy" }));
  assert.ok(!("error" in list));
  const contract = list.documents.find((d) => d.label === "smlouva_o_uveru")!;
  const result = await getDocument(createContext({ case_id: "mock-unhappy", document_id: contract.document_id }));
  assert.ok(!("error" in result));
  assert.equal(result.pages.length, contract.page_count);
  assert.equal(result.pages[0].page, 1);
  assert.match(result.pages[0].text, /IČ: YYYYYYY/);
});

test("an unknown document is not found", async () => {
  const context = createContext({ case_id: "mock-unhappy", document_id: "nope" });
  assert.deepEqual(await getDocument(context), { error: "document_not_found" });
  assert.equal(context.getStatus(), 404);
});

test("serves the Stavby Fišer fixture", async () => {
  const result = await getCase(createContext({ case_id: "mock-stavby-fiser" }, LIVE));
  assert.ok(!("error" in result));
  assert.equal(result.client?.ico, "25317688");
  const list = await listDocuments(createContext({ case_id: "mock-stavby-fiser" }));
  assert.ok(!("error" in list));
  assert.deepEqual(list.documents.map((d) => d.label).sort(), ["doklad_o_uhrade", "objednavka", "predavaci_protokol", "smlouva_o_uveru", "vinkulace_pojisteni", "zajistovaci_prevod"]);
});

test("a document's text does not carry its fixture signatures", async () => {
  const list = await listDocuments(createContext({ case_id: "mock-solom-rec" }));
  assert.ok(!("error" in list));
  const result = await getDocument(createContext({ case_id: "mock-solom-rec", document_id: list.documents[0].document_id }));
  assert.ok(!("error" in result));
  assert.ok(!("signatures" in result));
});

test("returns a fixture document's signatures by role and page", async () => {
  const list = await listDocuments(createContext({ case_id: "mock-unhappy" }));
  assert.ok(!("error" in list));
  const guarantee = list.documents.find((d) => d.label === "ruceni")!;
  const result = await getSignatures(createContext({ case_id: "mock-unhappy", document_id: guarantee.document_id }));
  assert.ok(!("error" in result));
  assert.deepEqual(result.signatures.map((s) => [s.role, s.page]), [["guarantor", 3], ["provider", 3]]);
  assert.match(result.signatures[1].evidence, /Jan Kovák/);
  assert.equal(result.signatures[1].copy_suspicion, "none");
});

test("live signatures use the documents API secret and adapt the upstream items", async () => {
  const calls = stubFetch({
    "https://api.example.test/v1/cases/case-1/documents/d1/signatures?match_client=true&include_vectors=false": {
      status: 200,
      body: { case_id: "case-1", document_id: "d1", signatures: [{ signature_id: "s1", page: 3, role: "borrower", role_evidence: "Příjemce: X", copy_suspicion: { level: "low", matches: [] } }] },
    },
  });
  const result = await getSignatures(createContext({ case_id: "case-1", document_id: "d1" }, LIVE));
  assert.deepEqual(result, { case_id: "case-1", document_id: "d1", is_mock: false, signatures: [{ page: 3, role: "borrower", evidence: "Příjemce: X", copy_suspicion: "low" }] });
  assert.equal(calls[0].secretName, "kb-aws-ingest-api-key");
});

test("signatures of an unknown document are not found", async () => {
  const context = createContext({ case_id: "mock-unhappy", document_id: "nope" });
  assert.deepEqual(await getSignatures(context), { error: "document_not_found" });
  assert.equal(context.getStatus(), 404);
});

test("serves a generated eval case, its documents and signatures", async () => {
  const result = await getCase(createContext({ case_id: "mock-eval-clean" }, LIVE));
  assert.ok(!("error" in result));
  assert.equal(result.client?.ico, "28456718");
  const list = await listDocuments(createContext({ case_id: "mock-eval-clean" }));
  assert.ok(!("error" in list));
  assert.equal(list.documents.length, 9);
  const document = await getDocument(createContext({ case_id: "mock-eval-clean", document_id: "agr-01" }));
  assert.ok(!("error" in document));
  assert.match(document.pages[0].text, /SMLOUVA O ÚVĚRU Č. 170555\/25/);
  assert.ok(!("errors" in document));
  const signatures = await getSignatures(createContext({ case_id: "mock-eval-clean", document_id: "agr-01" }));
  assert.ok(!("error" in signatures));
  assert.deepEqual(signatures.signatures.map((s) => s.role), ["provider", "provider", "borrower"]);
});

test("an eval case without a client record returns client null", async () => {
  const result = await getCase(createContext({ case_id: "mock-eval-no-client-record" }));
  assert.ok(!("error" in result));
  assert.equal(result.client, null);
});

test("a fixture's injected errors come back as upstream failures", async () => {
  const list = createContext({ case_id: "mock-eval-documents-down" });
  assert.deepEqual(await listDocuments(list), { error: "upstream", message: "documents API returned 503" });
  assert.equal(list.getStatus(), 502);
  const read = createContext({ case_id: "mock-eval-document-read-fails", document_id: "ruc-01" });
  assert.deepEqual(await getDocument(read), { error: "upstream", message: "documents API returned 503" });
  const signatures = createContext({ case_id: "mock-eval-signatures-unavailable", document_id: "ruc-01" });
  assert.deepEqual(await getSignatures(signatures), { error: "upstream", message: "documents API signatures returned 503" });
  assert.ok(!("error" in (await getDocument(createContext({ case_id: "mock-eval-signatures-unavailable", document_id: "ruc-01" })))));
});

const REGIONS_URL = "https://api.example.test/v1/cases/case-1/documents/d1/regions?include_geometry=true";

test("fixture documents have no regions computed", async () => {
  const list = await listDocuments(createContext({ case_id: "mock-unhappy" }));
  assert.ok(!("error" in list));
  const result = await getRegions(createContext({ case_id: "mock-unhappy", document_id: list.documents[0].document_id }));
  assert.deepEqual(result, { case_id: "mock-unhappy", document_id: list.documents[0].document_id, is_mock: true, status: "not_run", regions: [] });
});

test("regions of an unknown document are not found", async () => {
  const context = createContext({ case_id: "mock-unhappy", document_id: "nope" });
  assert.deepEqual(await getRegions(context), { error: "document_not_found" });
  assert.equal(context.getStatus(), 404);
});

test("live regions use the documents API secret and adapt the upstream items", async () => {
  const calls = stubFetch({
    [REGIONS_URL]: {
      status: 200,
      body: {
        case_id: "case-1", document_id: "d1", status: "completed",
        pages: [{ page: 1, width: 595, height: 842, source: "text_layer" }],
        regions: [
          {
            region_id: "p1-r07", page: 1, kind: "table_row", label: "smluvni_strana", party: "guarantor", summary: "IČO a DIČ ručitele", section: "p1-r04",
            text: "IČO / DIČ | 98001027 / CZ98001027", bbox: [0.079, 0.1717, 0.5569, 0.1819],
            lines: [{ bbox: [0.079, 0.1717, 0.1455, 0.1812], start: 0, end: 9 }, { bbox: [0.378, 0.1718, 0.5569, 0.1819], start: 12, end: 33 }],
          },
          { region_id: "p2-r01", page: 2, kind: "heading", label: null, text: "Článek 2", bbox: [0.1, 0.1, 0.3, 0.12], lines: [{ bbox: [0.1, 0.1, 0.3, 0.12], start: 0, end: 8 }] },
        ],
      },
    },
  });
  const result = await getRegions(createContext({ case_id: "case-1", document_id: "d1" }, LIVE));
  assert.deepEqual(result, {
    case_id: "case-1", document_id: "d1", is_mock: false, status: "completed",
    regions: [
      {
        region_id: "p1-r07", page: 1, label: "smluvni_strana", party: "guarantor", refers_to: [],
        text: "IČO / DIČ | 98001027 / CZ98001027", bbox: [0.079, 0.1717, 0.5569, 0.1819],
        lines: [{ bbox: [0.079, 0.1717, 0.1455, 0.1812], start: 0, end: 9 }, { bbox: [0.378, 0.1718, 0.5569, 0.1819], start: 12, end: 33 }],
      },
      { region_id: "p2-r01", page: 2, label: null, party: null, refers_to: [], text: "Článek 2", bbox: [0.1, 0.1, 0.3, 0.12] },
    ],
  });
  assert.equal(calls[0].secretName, "kb-aws-ingest-api-key");
});

test("regions that were not computed come back empty", async () => {
  stubFetch({ [REGIONS_URL]: { status: 200, body: { case_id: "case-1", document_id: "d1", status: "not_run", regions: [{ region_id: "p1-r01", page: 1, text: "x" }] } } });
  const result = await getRegions(createContext({ case_id: "case-1", document_id: "d1" }, LIVE));
  assert.ok(!("error" in result));
  assert.equal(result.status, "not_run");
  assert.deepEqual(result.regions, []);
});

test("a document still being ingested has regions not_ready, not an error", async () => {
  stubFetch({ [REGIONS_URL]: { status: 409, body: { error: "not ready" } } });
  const context = createContext({ case_id: "case-1", document_id: "d1" }, LIVE);
  const result = await getRegions(context);
  assert.ok(!("error" in result));
  assert.equal(result.status, "not_ready");
  assert.equal(context.getStatus(), 200);
});

test("a live regions failure is reported as 502", async () => {
  stubFetch({ [REGIONS_URL]: { status: 500, body: {} } });
  const context = createContext({ case_id: "case-1", document_id: "d1" }, LIVE);
  const result = await getRegions(context);
  assert.equal("error" in result && result.error, "upstream");
  assert.equal(context.getStatus(), 502);
});
