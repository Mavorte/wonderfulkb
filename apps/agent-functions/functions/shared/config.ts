// Tenant configuration shared by the case-evaluator functions.
//
// AWS group (one API serving cases, clients and documents):
// - global `case_eval_aws_mock`: "true" serves every case from the mock layer.
//   A case id that has a fixture (`mock-...`) is always served from it, so evals
//   work while live is on. An empty API URL also means mock.
// - global `case_eval_documents_api_url` + secret `kb-aws-ingest-api-key`: the
//   merged case/client and documents API (openapi-case-client.yaml,
//   documents_for_agent_api.json). It accepts the ingest key, so the functions
//   share that secret instead of keeping a copy.

export const API_URL = "case_eval_documents_api_url";
export const API_SECRET = "kb-aws-ingest-api-key";
export const AWS_MOCK = "case_eval_aws_mock";

export type GlobalsContext = { globals: { get(name: string): unknown } };

// Missing globals throw at runtime instead of returning null.
export function getGlobal(context: GlobalsContext, name: string): string {
  try {
    return String(context.globals.get(name) ?? "").trim();
  } catch {
    return "";
  }
}

export function getGlobalUrl(context: GlobalsContext, name: string): string {
  return getGlobal(context, name).replace(/\/+$/, "");
}

export function isSwitchOn(context: GlobalsContext, name: string): boolean {
  return ["true", "1", "yes", "on"].includes(getGlobal(context, name).toLowerCase());
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
