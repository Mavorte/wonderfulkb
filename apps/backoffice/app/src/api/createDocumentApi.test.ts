import assert from "node:assert/strict";
import { test } from "node:test";
import createDocumentApi from "./createDocumentApi.ts";

test("loads paginated company clients using the server's IDs and ICO strings", async () => {
  const paths: string[] = [];
  const api = createDocumentApi({ fetchImpl: async (input) => {
    paths.push(String(input));
    return Response.json({ clients: [{ client_id: paths.length === 1 ? "a" : "b", name: "Firma", ico: "00123456", status: "active" }], next_token: paths.length === 1 ? "second" : null });
  } });
  const clients = await api.getClients();
  assert.deepEqual(clients.map((c) => c.id), ["a", "b"]);
  assert.equal(clients[0].ico, "00123456");
  assert.match(paths[1], /next_token=second/);
});

test("preserves caller's idempotent case ID and sends no API key to the browser", async () => {
  const bodies: unknown[] = [];
  const api = createDocumentApi({ fetchImpl: async (_input, options) => {
    assert.equal(new Headers(options?.headers).has("x-api-key"), false);
    bodies.push(JSON.parse(String(options?.body)));
    return Response.json({ case_id: "case-stable" });
  } });
  await api.createCase("firm-uuid", "case-stable", ["invoice"]);
  await api.createCase("firm-uuid", "case-stable", ["invoice"]);
  assert.deepEqual(bodies[0], bodies[1]);
});

test("never starts OCR if upload fails", async () => {
  const paths: string[] = [];
  const api = createDocumentApi({ fetchImpl: async (input) => {
    paths.push(String(input));
    if (paths.length === 1) return Response.json({ document: { document_id: "d" }, upload: { url: "https://upload.example.test/object", method: "PUT", headers: {} } });
    return new Response("", { status: 500 });
  } });
  await assert.rejects(api.upload("case-a", new File(["pdf"], "a.pdf", { type: "application/pdf" }), "visual"));
  assert.equal(paths.some((p) => p.endsWith("/complete")), false);
});

test("binds corrections to their original document, run and field", async () => {
  let sent: unknown;
  const api = createDocumentApi({ fetchImpl: async (_input, options) => {
    sent = JSON.parse(String(options?.body));
    return Response.json({});
  } });
  await api.correct("case-a", "doc-a", "run-a", "field-a", "00123456", "Kontrola originálu");
  assert.deepEqual(sent, { run_id: "run-a", field_id: "field-a", normalized_value: "00123456", reason: "Kontrola originálu" });
});
