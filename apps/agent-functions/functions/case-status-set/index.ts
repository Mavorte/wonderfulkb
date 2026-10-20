// Sets a case's status (body: case_id, status; one of the seven in functions/shared/caseData.ts). See functions/shared/config.ts for the live/mock configuration.

import type { FunctionContext } from "@wonderful/types";
import { setCaseStatus } from "../shared/caseData.ts";

async function userFunction(context: FunctionContext) {
  return setCaseStatus(context);
}
