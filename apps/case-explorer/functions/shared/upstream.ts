// Shared by the explorer functions: calls the AWS APIs and the evaluator webhook
// with keys attached server-side, and returns the upstream status and body as is,
// so the app can show exactly what each API answered.
//
// Configuration (tenant-level):
// - global `case_eval_documents_api_url` + secret `kb-aws-ingest-api-key`: the
//   AWS API serving cases, clients and documents (openapi-case-client.yaml,
//   documents_for_agent_api.json).
// - secret `case_eval_webhook_secret` (header X-Webhook-Secret): the case-evaluator
//   webhook trigger EVALUATOR_WEBHOOK_URL.

import type { FunctionContext } from "@wonderful/types";

export const API_URL = "case_eval_documents_api_url";
export const API_SECRET = "kb-aws-ingest-api-key";
export const EVALUATOR_WEBHOOK_URL =
  "https://api.sb.wonderful.ai/api/v1/tasks/webhook/062b5032-a738-48c9-810e-b726788add38";
export const EVALUATOR_WEBHOOK_SECRET = "case_eval_webhook_secret";

const TIMEOUT_MS = 10000;

export type UpstreamResult = {
  url: string;
  status: number;
  ok: boolean;
  body: unknown;
  secret?: string;
  error?: string;
};

// Missing globals throw at runtime instead of returning null.
export function getGlobalUrl(context: FunctionContext, name: string): string {
  try {
    return String(context.globals.get(name) ?? "").trim().replace(/\/+$/, "");
  } catch {
    return "";
  }
}

export function getParam(context: FunctionContext, name: string): string {
  return String(context.data?.[name] ?? "").trim();
}

export function getQuery(params: Record<string, string | undefined>): string {
  const pairs = Object.entries(params).filter(([, value]) => value);
  if (!pairs.length) return "";
  return "?" + pairs.map(([key, value]) => `${key}=${encodeURIComponent(value as string)}`).join("&");
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// The runtime's fetch sometimes fails with "NetworkError" before reaching the
// API, and an immediate retry succeeds. GETs are retried once; a POST is not,
// because it may have reached the server (the webhook would start a second task).
export async function callUpstream(
  url: string,
  secretName: string,
  init: { method?: string; body?: unknown } = {},
): Promise<UpstreamResult> {
  const result = await callUpstreamOnce(url, secretName, init);
  if (result.status !== 0 || (init.method ?? "GET") !== "GET") return result;
  return callUpstreamOnce(url, secretName, init);
}

async function callUpstreamOnce(
  url: string,
  secretName: string,
  init: { method?: string; body?: unknown },
): Promise<UpstreamResult> {
  try {
    const response = await fetch(url, {
      method: init.method ?? "GET",
      headers: { accept: "application/json", ...(init.body ? { "content-type": "application/json" } : {}) },
      body: init.body ? JSON.stringify(init.body) : undefined,
      secretName,
      timeoutMs: TIMEOUT_MS,
    });
    const text = await response.text();
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      // Not JSON: keep the raw text.
    }
    return { url, status: response.status, ok: response.ok, body, secret: secretName };
  } catch (error) {
    return { url, status: 0, ok: false, body: null, secret: secretName, error: getErrorMessage(error) };
  }
}

export async function callAwsApi(context: FunctionContext, path: string): Promise<UpstreamResult> {
  const baseUrl = getGlobalUrl(context, API_URL);
  if (!baseUrl) return notConfigured(API_URL);
  return callUpstream(`${baseUrl}${path}`, API_SECRET);
}

function notConfigured(globalName: string): UpstreamResult {
  return { url: "", status: 0, ok: false, body: null, error: `global ${globalName} is not set` };
}

// Functions answer 200 and carry the problem in the result, so the app shows
// every outcome the same way.
export function missingParameter(name: string): UpstreamResult {
  return { url: "", status: 400, ok: false, body: null, error: `missing parameter: ${name}` };
}
