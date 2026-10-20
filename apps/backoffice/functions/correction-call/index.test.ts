import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { getContactLastName, userFunction } from "./index.ts";

type Row = Record<string, unknown>;
type Filter = { column: string; operator: string; value: unknown };

const GLOBALS: Row = {
  correction_call_destination: "+420607783995",
  correction_call_from_number: "+420910920694",
  public_access_base_url: "https://intake.example/",
};

const CASE = {
  case_id: "C1",
  case: { metadata: { client_name: "Plastovra Výroba s.r.o." } },
  client: { name: "Plastovra Výroba s.r.o.", signatories: [{ name: "Dalibor Křemeník", function: "jednatel" }] },
};

const FINDINGS = [{ label: "Invoice", found: "Buyer is a different company" }];

// Stands in for globals, tables, the case Function and the platform API; records the outbound calls.
function createContext(options: { data: Row; globals?: Row; evalCase?: Row; links?: Row[]; callFails?: boolean }) {
  let status = 200;
  const tables: Record<string, { id: string; data: Row }[]> = {
    "client_intake.intake_links": (options.links ?? []).map((data) => ({ id: String(data.hash), data })),
    "backoffice.correction_calls": [],
  };
  const calls: Row[] = [];
  const context = {
    data: options.data,
    metadata: { user: { id: "u1", email: "reviewer@kb.example" } },
    response: { setStatus: (code: number) => (status = code) },
    globals: { get: (name: string) => (options.globals ?? GLOBALS)[name] },
    functions: { run: () => ({ result: options.evalCase ?? CASE }) },
    tables: {
      filter: async (table: string, filters: Filter[]) => ({
        rows: tables[table].filter((row) => filters.every((f) => row.data[f.column] === f.value)),
      }),
      insert: async (table: string, data: Row) => {
        const row = { id: `${table}-${tables[table].length}`, data };
        tables[table].push(row);
        return row;
      },
      update: async (table: string, id: string, data: Row) => {
        const row = tables[table].find((r) => r.id === id)!;
        Object.assign(row.data, data);
        return row;
      },
    },
    api: {
      post: async (path: string, { body }: { body: Row }) => {
        calls.push({ path, ...body });
        if (options.callFails) throw new Error("403 forbidden");
        return { communication_id: "comm-1" };
      },
    },
  };
  return {
    context: context as unknown as FunctionContext,
    status: () => status,
    calls,
    requests: () => tables["backoffice.correction_calls"].map((r) => r.data),
    links: () => tables["client_intake.intake_links"].map((r) => r.data),
  };
}

test("correction-call records the request and calls the configured number from the agent's number", async () => {
  const env = createContext({
    data: { case_id: "C1", findings: FINDINGS, note: "Ask for the corrected invoice" },
    links: [{ hash: "abc", case_id: "C1", inserted_at: 1 }],
  });
  const body = await userFunction(env.context);

  assert.equal(env.status(), 200);
  assert.deepEqual(body, { request_id: (body as { request_id: string }).request_id, status: "calling", phone_number: "+420607783995", communication_id: "comm-1" });
  assert.equal(env.calls.length, 1);
  assert.equal(env.calls[0].path, "/v1/agents/outbound");
  assert.equal(env.calls[0].from, "+420910920694");
  assert.equal(env.calls[0].to, "+420607783995");

  const [request] = env.requests();
  assert.equal(request.status, "pending");
  assert.equal(request.phone_number, "+420607783995");
  assert.equal(request.contact_last_name, "Křemeník");
  assert.equal(request.upload_link, "https://intake.example?h=abc");
  assert.deepEqual(JSON.parse(String(request.findings)), FINDINGS);
  assert.equal(request.requested_by, "reviewer@kb.example");
  assert.equal(env.links().length, 1, "the existing intake link is reused");
});

test("correction-call gives a case without an intake link a new one", async () => {
  const env = createContext({ data: { case_id: "C1", findings: FINDINGS } });
  await userFunction(env.context);
  const [link] = env.links();
  assert.equal(link.case_id, "C1");
  assert.equal(env.requests()[0].upload_link, `https://intake.example?h=${link.hash}`);
});

test("correction-call marks the request failed when the call cannot be placed", async () => {
  const env = createContext({ data: { case_id: "C1", findings: FINDINGS }, callFails: true });
  const body = await userFunction(env.context);
  assert.equal(env.status(), 502);
  assert.equal((body as { error: string }).error, "call_failed");
  assert.equal(env.requests()[0].status, "call_failed");
});

test("correction-call rejects bad input and missing configuration before calling", async () => {
  for (const data of [{ findings: FINDINGS }, { case_id: "C1" }, { case_id: "C1", findings: [] }, { case_id: "C1", findings: [{ found: "x" }] }]) {
    const env = createContext({ data });
    assert.deepEqual(await userFunction(env.context), { error: "bad_request" });
    assert.equal(env.status(), 400);
    assert.equal(env.calls.length, 0);
  }

  const unconfigured = createContext({ data: { case_id: "C1", findings: FINDINGS }, globals: {} });
  assert.equal(((await userFunction(unconfigured.context)) as { error: string }).error, "not_configured");

  const noContact = createContext({ data: { case_id: "C1", findings: FINDINGS }, evalCase: { ...CASE, client: { signatories: [] } } });
  assert.equal(((await userFunction(noContact.context)) as { error: string }).error, "no_contact");
  assert.equal(noContact.status(), 409);
  assert.equal(noContact.calls.length, 0);

  const missing = createContext({ data: { case_id: "C1", findings: FINDINGS }, evalCase: { error: "case_not_found" } });
  assert.equal(((await userFunction(missing.context)) as { error: string }).error, "case_not_found");
  assert.equal(missing.status(), 404);
});

test("getContactLastName takes the first signatory's surname", () => {
  assert.equal(getContactLastName(CASE), "Křemeník");
  assert.equal(getContactLastName({ client: { signatories: [{ name: "  Novák " }] } }), "Novák");
  assert.equal(getContactLastName({ client: null }), null);
});
