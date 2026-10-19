// Calls the AWS case/client API (openapi-case-client.yaml).
//
// Configuration (tenant-level):
// - global `case_eval_documents_api_url`: base URL of the API, e.g. `https://<id>.execute-api.eu-central-1.amazonaws.com/v1`.
// - secret `kb-aws-ingest-api-key` (type "API Key"): its `header_name` and `api_key`
//   authenticate the request to API Gateway.

import type { FunctionContext } from "@wonderful/types";

const URL_GLOBAL = "case_eval_documents_api_url";
const SECRET_NAME = "kb-aws-ingest-api-key";
const TIMEOUT_MS = 8000;

export type AwsResponse<T> = { status: number; ok: boolean; body: T | null };

/** Case as returned by the AWS API. */
export type AwsCase = {
  case_id: string;
  client_id: string;
  status: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

/** Case as the backoffice lists it. The client's name and IČO come from the metadata case-create stores. */
export type CaseSummary = {
  case_id: string;
  client_id: string;
  client_name: string | null;
  client_ico: string | null;
  status: string;
  created_at: string;
};

/** Sends a JSON request to the AWS API; a missing global, secret, or network failure throws. */
export async function requestAwsApi<T>(
  context: FunctionContext,
  path: string,
  init: { method?: "GET" | "POST"; body?: unknown } = {},
): Promise<AwsResponse<T>> {
  const baseUrl = String(context.globals.get(URL_GLOBAL) ?? "").replace(/\/+$/, "");
  if (!baseUrl) throw new Error(`global ${URL_GLOBAL} is not set`);
  const secret: { header_name?: string; api_key?: string } = context.secrets.get(SECRET_NAME) ?? {};
  const response = await fetch(`${baseUrl}${path}`, {
    method: init.method ?? "GET",
    headers: {
      [secret.header_name || "x-api-key"]: secret.api_key ?? "",
      accept: "application/json",
      ...(init.body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    timeoutMs: TIMEOUT_MS,
  });
  const text = await response.text();
  let body: T | null = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) console.log(`AWS API ${init.method ?? "GET"} ${path} returned ${response.status}: ${text.slice(0, 200)}`);
  return { status: response.status, ok: response.ok, body };
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

export function toCaseSummary(awsCase: AwsCase): CaseSummary {
  return {
    case_id: awsCase.case_id,
    client_id: awsCase.client_id,
    client_name: getString(awsCase.metadata?.client_name),
    client_ico: getString(awsCase.metadata?.ico),
    status: awsCase.status,
    created_at: awsCase.created_at,
  };
}
