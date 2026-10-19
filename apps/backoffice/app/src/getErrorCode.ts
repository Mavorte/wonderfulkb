/**
 * Returns the `error` code a Function responded with. invokeFunction throws on
 * a non-2xx status: in an external app with the code as the message, inside
 * Wonderful as an axios error carrying the response body.
 */
export default function getErrorCode(error: unknown): string | undefined {
  const data = (error as { response?: { data?: { error?: unknown } } } | null)?.response?.data;
  if (typeof data?.error === "string") return data.error;
  return error instanceof Error ? error.message : undefined;
}
