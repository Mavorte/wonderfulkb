import assert from "node:assert/strict";
import { test } from "node:test";
import createDocumentProxy from "../runner/createDocumentProxy.ts";

test("proxy injects server key and does not forward browser authorization", async (t) => {
  const proxy = createDocumentProxy({ documentApiUrl: "https://documents.example.test", documentApiKey: "server-key" });
  t.mock.method(globalThis, "fetch", async (input, options) => {
    assert.equal(String(input), "https://documents.example.test/v1/cases/a/documents");
    assert.equal(options.headers.get("x-api-key"), "server-key");
    assert.equal(options.headers.has("authorization"), false);
    assert.equal(options.headers.has("cookie"), false);
    return Response.json({ documents: [] });
  });
  let status;
  const response = { writeHead(code) { status = code; }, end() {} };
  await proxy({ method: "GET", headers: { authorization: "untrusted", cookie: "untrusted" } }, response,
    new URL("https://ui.example.test/document-api/v1/cases/a/documents"));
  assert.equal(status, 200);
});

test("client lookup uses the separate case-client backend", async (t) => {
  const proxy = createDocumentProxy({ documentApiUrl: "https://documents.example.test", caseClientApiUrl: "https://clients.example.test", caseClientApiKey: "client-key" });
  t.mock.method(globalThis, "fetch", async (input, options) => {
    assert.equal(new URL(input).hostname, "clients.example.test");
    assert.equal(options.headers.get("x-api-key"), "client-key");
    return Response.json({ clients: [] });
  });
  await proxy({ method: "GET", headers: {} }, { writeHead() {}, end() {} }, new URL("https://ui.example.test/document-api/v1/clients"));
});
