// Calls a case-evaluator Function in the agent-functions app. The Functions own
// the API access, secrets and mock switches; see repos/agent-functions/README.md.

type FunctionsContext = {
  functions: { run(options: { slug: string; params?: Record<string, unknown> }): { result: Record<string, any> } };
};

export type FunctionError = { error: string; message?: string };

// Functions are addressed by "<app slug>/<path_slug>".
const APP = "agent-functions";

export function runFunction<T>(ctx: FunctionsContext, slug: string, params: Record<string, unknown>): T | FunctionError {
  try {
    return ctx.functions.run({ slug: `${APP}/${slug}`, params }).result as T;
  } catch (error) {
    return { error: "function_failed", message: describeError(error) };
  }
}

export function isError(value: unknown): value is FunctionError {
  return typeof value === "object" && value !== null && "error" in value;
}

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}
