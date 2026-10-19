// Returns a case and its client for the case-evaluator agent (body: case_id). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { getCase } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return getCase(context);
}
