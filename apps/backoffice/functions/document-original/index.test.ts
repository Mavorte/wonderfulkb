import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { userFunction } from "./index.ts";

const ORIGINAL = "/v1/cases/C1/documents/d1/original";

// Stands in for the AWS API: answers by path and records each requested path.
function stubFetch(upstream: Record<string, { status: number; body: unknown }>) {
  const paths: string[] = [];
  globalThis.fetch = (async (url: string) => {
    paths.push(new URL(url).pathname);
    const hit = upstream[new URL(url).pathname] ?? { status: 404, body: { error: "Originál dokumentu neexistuje" } };
    return new Response(JSON.stringify(hit.body), { status: hit.status });
  }) as unknown as typeof fetch;
  return paths;
}

// Captures the audit lines the function logs.
function captureLogs() {
  const lines: string[] = [];
  const original = console.log;
  console.log = (line: string) => lines.push(line);
  return { lines, restore: () => (console.log = original) };
}

function createContext(data: unknown, user: { id: string } | null = { id: "u1" }) {
  let status = 200;
  const context = {
    data,
    user: user ?? undefined,
    response: { setStatus: (code: number) => (status = code) },
    globals: { get: () => "https://aws.test/v1" },
    secrets: { get: () => ({ header_name: "x-api-key", api_key: "k" }) },
  };
  // The function only touches data, user, response, globals and secrets.
  return { context: context as unknown as FunctionContext, status: () => status };
}

test("document-original returns the short-lived link and audits the user", async () => {
  const paths = stubFetch({
    [ORIGINAL]: {
      status: 200,
      body: { case_id: "C1", document_id: "d1", filename: "0_Smlouva.pdf", content_type: "application/pdf", url: "https://s3/o.pdf?sig", expires_in: 60 },
    },
  });
  const logs = captureLogs();
  const { context, status } = createContext({ case_id: "C1", document_id: "d1" });
  const body = await userFunction(context);
  logs.restore();

  assert.equal(status(), 200);
  assert.deepEqual(body, { filename: "0_Smlouva.pdf", contentType: "application/pdf", url: "https://s3/o.pdf?sig", expiresIn: 60 });
  assert.deepEqual(paths, [ORIGINAL]);
  assert.deepEqual(JSON.parse(logs.lines[0]), { event: "document_reveal", user_id: "u1", case_id: "C1", document_id: "d1", outcome: "revealed" });
  assert.ok(logs.lines.every((l) => !l.includes("https://s3")));
});

test("document-original answers 404, 502, 401 and 400", async () => {
  stubFetch({});
  const logs = captureLogs();
  const missing = createContext({ case_id: "C1", document_id: "d1" });
  assert.deepEqual(await userFunction(missing.context), { error: "not_found" });
  assert.equal(missing.status(), 404);
  assert.equal(JSON.parse(logs.lines.at(-1) as string).outcome, "not_found");

  stubFetch({ [ORIGINAL]: { status: 500, body: { error: "Interní chyba služby" } } });
  const failed = createContext({ case_id: "C1", document_id: "d1" });
  assert.deepEqual(await userFunction(failed.context), { error: "upstream" });
  assert.equal(failed.status(), 502);
  assert.equal(JSON.parse(logs.lines.at(-1) as string).outcome, "error");

  const paths = stubFetch({});
  const anonymous = createContext({ case_id: "C1", document_id: "d1" }, null);
  assert.deepEqual(await userFunction(anonymous.context), { error: "unauthenticated" });
  assert.equal(anonymous.status(), 401);

  for (const data of [{ case_id: "C1" }, { case_id: "C1", document_id: "../x" }, { case_id: "a/b", document_id: "d1" }]) {
    const bad = createContext(data);
    assert.deepEqual(await userFunction(bad.context), { error: "bad_request" });
    assert.equal(bad.status(), 400);
  }
  logs.restore();
  assert.deepEqual(paths, []);
});
