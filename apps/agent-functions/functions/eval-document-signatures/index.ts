// Returns the signatures detected in one document for the case-evaluator agent (body: case_id, document_id). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { getSignatures } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return getSignatures(context);
}
