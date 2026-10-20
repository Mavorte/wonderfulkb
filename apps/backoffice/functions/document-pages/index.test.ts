import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { userFunction } from "./index.ts";

type Upstream = Record<string, { status: number; body: unknown }>;

// Stands in for the AWS API: answers by path and records each request.
function stubFetch(upstream: Upstream) {
  const calls: { url: string; key: string | undefined }[] = [];
  globalThis.fetch = (async (url: string, init: { headers: Record<string, string> }) => {
    calls.push({ url, key: init.headers["x-api-key"] });
    const hit = upstream[new URL(url).pathname] ?? { status: 404, body: { error: "Dokument neexistuje" } };
    return new Response(JSON.stringify(hit.body), { status: hit.status });
  }) as unknown as typeof fetch;
  return calls;
}

function createContext(data: unknown) {
  let status = 200;
  const context = {
    data,
    response: { setStatus: (code: number) => (status = code) },
    globals: { get: (name: string) => (name === "case_eval_documents_api_url" ? "https://aws.test/v1/" : undefined) },
    secrets: { get: () => ({ header_name: "x-api-key", api_key: "k" }) },
  };
  // The function only touches data, response, globals and secrets.
  return { context: context as unknown as FunctionContext, status: () => status };
}

const pages = (documentId: string) => ({
  case_id: "C1",
  document_id: documentId,
  page_count: 3,
  redacted: true,
  preview_pdf_url: "https://s3/redacted.pdf",
  pages: [
    { page: 1, preview_url: "https://s3/1.png" },
    { page: 2, preview_url: null },
    { page: 3, preview_url: "https://s3/3.png" },
  ],
  original_available: true,
  reveal_path: `/cases/C1/documents/${documentId}/original`,
});

test("document-pages returns each document's masked pages in request order", async () => {
  const calls = stubFetch({
    "/v1/cases/C1/documents/d1/pages": { status: 200, body: pages("d1") },
    "/v1/cases/C1/documents/d2/pages": { status: 409, body: { error: "OCR ještě nedoběhlo", processing_status: "queued" } },
  });
  const { context, status } = createContext({ case_id: "C1", document_ids: ["d1", "d2", "d3", "d1"] });
  const body = await userFunction(context);

  assert.equal(status(), 200);
  assert.deepEqual(body, {
    documents: [
      {
        documentId: "d1",
        status: "ready",
        redacted: true,
        pdfUrl: "https://s3/redacted.pdf",
        pages: ["https://s3/1.png", null, "https://s3/3.png"],
        originalAvailable: true,
      },
      { documentId: "d2", status: "processing" },
      { documentId: "d3", status: "not_found" },
    ],
  });
  assert.equal(calls.length, 3);
  assert.ok(calls.every((c) => c.key === "k" && !c.url.includes("/original")));
});

test("document-pages marks only the failing document and answers 400 for malformed ids", async () => {
  stubFetch({
    "/v1/cases/C1/documents/d1/pages": { status: 500, body: { error: "Interní chyba služby" } },
    "/v1/cases/C1/documents/d2/pages": { status: 200, body: pages("d2") },
  });
  const partial = createContext({ case_id: "C1", document_ids: ["d1", "d2"] });
  const body = (await userFunction(partial.context)) as { documents: { status: string }[] };
  assert.equal(partial.status(), 200);
  assert.deepEqual(body.documents.map((d) => d.status), ["error", "ready"]);

  for (const data of [{ case_id: "C1" }, { case_id: "../x", document_ids: [] }, { case_id: "C1", document_ids: ["a/b"] }]) {
    const bad = createContext(data);
    assert.deepEqual(await userFunction(bad.context), { error: "bad_request" });
    assert.equal(bad.status(), 400);
  }
});
