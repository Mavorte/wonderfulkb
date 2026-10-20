// Returns one document's regions (labelled paragraphs and table rows with their text and position) for the case-evaluator agent (body: case_id, document_id). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { getRegions } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return getRegions(context);
}
