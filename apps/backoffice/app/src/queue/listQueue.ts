import type { useWonderful } from "@wonderful/app-sdk";
import type { QueueCase } from "./triage";

export type QueuePayload = { cases: QueueCase[]; truncated: boolean };

type Api = ReturnType<typeof useWonderful>["api"];

type CaseQueueResponse =
  | { cases: QueueCase[]; truncated: boolean; error?: undefined }
  | { error: string };

/** Lists every evaluated case with its latest run and client, from the case-queue function. */
export default async function listQueue(api: Api): Promise<QueuePayload> {
  const result = await api.invokeFunction<CaseQueueResponse>("backoffice/case-queue", { method: "GET" });
  if (result.error !== undefined) throw new Error(result.error);
  return { cases: result.cases, truncated: result.truncated };
}
