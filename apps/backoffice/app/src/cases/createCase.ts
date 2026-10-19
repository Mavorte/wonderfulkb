import type { useWonderful } from "@wonderful/app-sdk";
import type { Client } from "../clients/mockClients";

export type Case = { id: string; clientId: string; hash: string; createdAt: string };

type Api = ReturnType<typeof useWonderful>["api"];

type CaseCreateResponse =
  | { case_id: string; client_id: string; hash: string; created_at: string; error?: undefined }
  | { error: string };

/** Creates a mocked case and registers its Client Intake link. */
export default async function createCase(api: Api, client: Client): Promise<Case> {
  const result = await api.invokeFunction<CaseCreateResponse>("backoffice/case-create", {
    method: "POST",
    params: { client_id: client.id },
  });
  if (result.error !== undefined) throw new Error(result.error);
  return { id: result.case_id, clientId: result.client_id, hash: result.hash, createdAt: result.created_at };
}
