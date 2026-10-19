// Searches clients in the AWS case/client API for the new-case autocomplete.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi } from "../lib/awsApi";
import { createClientsQuery, toClientOption, type ClientOption, type UpstreamClient } from "./query";

type ClientsListResponse = { clients: ClientOption[] } | { error: "upstream" };

async function userFunction(context: FunctionContext): Promise<ClientsListResponse> {
  const query = createClientsQuery(String(context.data?.q ?? ""));
  if (query === null) return { clients: [] };

  try {
    const response = await requestAwsApi<{ clients?: UpstreamClient[] }>(context, `/clients?${query}`);
    if (response.ok && response.body) return { clients: (response.body.clients ?? []).map(toClientOption) };
  } catch (error) {
    console.log(`clients API request failed: ${getErrorMessage(error)}`);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
