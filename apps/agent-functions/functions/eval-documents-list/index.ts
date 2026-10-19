// Lists a case's documents for the case-evaluator agent (body: case_id). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { listDocuments } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return listDocuments(context);
}
