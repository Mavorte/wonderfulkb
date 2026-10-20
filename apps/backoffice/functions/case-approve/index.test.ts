import { test } from "node:test";
import assert from "node:assert/strict";
import type { FunctionContext } from "@wonderful/types";
import { userFunction } from "./index.ts";

type Row = Record<string, unknown>;

// Stands in for the case Functions; records the status updates.
function createContext(options: { data: Row; evalCase?: Row; statusResult?: Row }) {
  let status = 200;
  const statusSets: Row[] = [];
  const context = {
    data: options.data,
    response: { setStatus: (code: number) => (status = code) },
    functions: {
      run: ({ slug, params }: { slug: string; params: Row }) => {
        if (slug === "agent-functions/eval-case-get") return { result: options.evalCase ?? { case_id: params.case_id, case: { status: "awaiting_decision" } } };
        statusSets.push({ slug, ...params });
        return { result: options.statusResult ?? { case_id: params.case_id, case: { status: params.status } } };
      },
    },
  };
  return { context: context as unknown as FunctionContext, status: () => status, statusSets };
}

test("case-approve moves a case awaiting a decision to approved", async () => {
  const env = createContext({ data: { case_id: "C1" } });
  assert.deepEqual(await userFunction(env.context), { case_id: "C1", status: "approved" });
  assert.equal(env.status(), 200);
  assert.deepEqual(env.statusSets, [{ slug: "agent-functions/case-status-set", case_id: "C1", status: "approved" }]);
});

test("case-approve refuses a case that is not awaiting a decision", async () => {
  for (const current of ["open", "evaluating", "awaiting_clarification", "approved", "completed"]) {
    const env = createContext({ data: { case_id: "C1" }, evalCase: { case: { status: current } } });
    assert.equal(((await userFunction(env.context)) as { error: string }).error, "not_awaiting_decision");
    assert.equal(env.status(), 409);
    assert.equal(env.statusSets.length, 0);
  }
});

test("case-approve reports a missing case, bad input and a failed status update", async () => {
  const missing = createContext({ data: { case_id: "C1" }, evalCase: { error: "case_not_found" } });
  assert.equal(((await userFunction(missing.context)) as { error: string }).error, "case_not_found");
  assert.equal(missing.status(), 404);

  const bad = createContext({ data: {} });
  assert.deepEqual(await userFunction(bad.context), { error: "bad_request" });
  assert.equal(bad.status(), 400);

  const failed = createContext({ data: { case_id: "C1" }, statusResult: { error: "upstream" } });
  assert.deepEqual(await userFunction(failed.context), { error: "upstream", message: "upstream" });
  assert.equal(failed.status(), 502);
});
