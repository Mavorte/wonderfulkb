// Lists clients (body: optional ico, name, status, next_token). See ../shared/upstream.ts for configuration.

import type { FunctionContext } from "@wonderful/types";
import { callAwsApi, getParam, getQuery } from "../shared/upstream";

async function userFunction(context: FunctionContext) {
  const query = getQuery({
    ico: getParam(context, "ico"),
    name: getParam(context, "name"),
    status: getParam(context, "status"),
    next_token: getParam(context, "next_token"),
    limit: "100",
  });
  return callAwsApi(context, `/clients${query}`);
}
