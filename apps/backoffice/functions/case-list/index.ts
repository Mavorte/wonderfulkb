// Lists all cases from the AWS case/client API, newest first. `next_token`
// from a previous response loads the next page.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi, toCaseSummary, type AwsCase, type CaseSummary } from "../lib/awsApi";

const PAGE_SIZE = 50;

type CaseListResponse = { cases: CaseSummary[]; next_token: string | null } | { error: "upstream" };

async function userFunction(context: FunctionContext): Promise<CaseListResponse> {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
  const nextToken = String(context.data?.next_token ?? "");
  if (nextToken) params.set("next_token", nextToken);

  try {
    const response = await requestAwsApi<{ cases?: AwsCase[]; next_token?: string | null }>(context, `/cases?${params}`);
    if (response.ok && response.body) {
      return { cases: (response.body.cases ?? []).map(toCaseSummary), next_token: response.body.next_token ?? null };
    }
  } catch (error) {
    console.log(`case list request failed: ${getErrorMessage(error)}`);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
