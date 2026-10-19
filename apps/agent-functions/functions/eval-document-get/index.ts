// Returns one document's page texts for the case-evaluator agent (body: case_id, document_id). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { getDocument } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return getDocument(context);
}
