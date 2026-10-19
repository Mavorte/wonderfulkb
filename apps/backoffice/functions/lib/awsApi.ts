// Calls the AWS case/client API (be-document-processing/contracts/openapi-validator-agent.yaml).
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

const PAGE_SIZE = 100;
// Bounds each walk at 1 000 records so a function stays well inside its timeout.
const MAX_PAGES = 10;

export type Page<T> = { items: T[]; truncated: boolean };

/** Reads every page of a list endpoint; `truncated` is set when the walk hit MAX_PAGES. */
export async function listAll<T>(context: FunctionContext, path: string, key: "clients" | "cases"): Promise<Page<T>> {
  const items: T[] = [];
  let nextToken: string | null = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (nextToken) params.set("next_token", nextToken);
    const response = await requestAwsApi<Record<string, unknown>>(context, `${path}?${params}`);
    if (!response.ok || !response.body) throw new Error(`${path} returned ${response.status}`);
    items.push(...((response.body[key] as T[] | undefined) ?? []));
    const token = response.body.next_token;
    nextToken = typeof token === "string" && token ? token : null;
    if (!nextToken) return { items, truncated: false };
  }
  return { items, truncated: true };
}
