// Lists a client's cases, newest first (body: client_id, optional next_token).

import type { FunctionContext } from "@wonderful/types";
import { callAwsApi, getParam, getQuery, missingParameter } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const clientId = getParam(context, "client_id");
  if (!clientId) return missingParameter("client_id");
  const query = getQuery({ next_token: getParam(context, "next_token"), limit: "100" });
  return callAwsApi(context, `/clients/${encodeURIComponent(clientId)}/cases${query}`);
}
