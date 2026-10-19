import assert from "node:assert/strict";
import { test } from "node:test";
import type { WonderfulAPI } from "@wonderful/app-sdk";
import createDocumentApi from "../api/createDocumentApi.ts";
import { mockClients } from "../clients/mockClients.ts";
import createCase from "./createCase.ts";

const client = mockClients[0];

function createBackend(calls: string[] = [], fail = false) {
  return createDocumentApi({ fetchImpl: async (_input, options) => {
    const body = JSON.parse(String(options?.body));
    calls.push(body.case_id);
    if (fail) return Response.json({ error: "UPSTREAM" }, { status: 503 });
    return Response.json({ ...body, status: "open", created_at: "2026-10-19T00:00:00Z" });
  } });
}

function createIntake(run: (params?: Record<string, unknown>) => unknown): Pick<WonderfulAPI, "invokeFunction"> {
  return { async invokeFunction<T>(slug: string, options?: { params?: Record<string, unknown> }) {
    assert.equal(slug, "backoffice/case-create");
    return run(options?.params) as T;
  } };
}

test("registers intake against the same persisted OCR case, keeping metadata and hash", async () => {
  const calls: string[] = [];
  const result = await createCase(client, "case-stable", ["invoice"], createBackend(calls), createIntake((params) => {
    assert.deepEqual(calls, ["case-stable"]);
    assert.deepEqual(params, { case_id: "case-stable", client_id: client.id });
    return { ...params, hash: "intake-hash", created_at: "2026-10-19T01:00:00Z" };
  }));
  assert.equal(result.case.case_id, "case-stable");
  assert.equal(result.case.hash, "intake-hash");
  assert.equal(result.case.created_at, "2026-10-19T00:00:00Z");
  assert.deepEqual(result.case.metadata, { required_document_types: ["invoice"] });
  assert.equal(result.intakeError, undefined);
});

test("a failed intake registration preserves the case and retries using the same ID", async () => {
  const calls: string[] = [];
  const backend = createBackend(calls);
  const failed = await createCase(client, "case-stable", ["invoice"], backend, createIntake(() => { throw new Error("offline"); }));
  assert.equal(failed.case.case_id, "case-stable");
  assert.equal(failed.intakeError, "offline");
  const recovered = await createCase(client, "case-stable", ["invoice"], backend, createIntake((params) => ({ ...params, hash: "retry-hash" })));
  assert.equal(recovered.case.hash, "retry-hash");
  assert.deepEqual(calls, ["case-stable", "case-stable"]);
});

test("never registers a link when the case backend rejects creation", async () => {
  let invoked = false;
  await assert.rejects(createCase(client, "case-stable", [], createBackend([], true), createIntake(() => { invoked = true; })));
  assert.equal(invoked, false);
});

test("rejects an intake response pointing to a different case", async () => {
  const result = await createCase(client, "case-stable", [], createBackend(), createIntake(() => ({ case_id: "wrong", client_id: client.id, hash: "wrong-hash" })));
  assert.equal(result.case.case_id, "case-stable");
  assert.equal(result.case.hash, undefined);
  assert.equal(result.intakeError, "INTAKE_CASE_MISMATCH");
});
