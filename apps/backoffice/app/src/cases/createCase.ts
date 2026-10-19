import createDocumentApi from "../api/createDocumentApi.ts";
import type { Client } from "../clients/mockClients.ts";

export type Case = { case_id: string; client_id: string; status: "open"; created_at: string; metadata?: Record<string, unknown> };

export default function createCase(client: Client, caseId: string, requiredDocumentTypes: string[], api = createDocumentApi()): Promise<Case> {
  return api.createCase(client.id, caseId, requiredDocumentTypes);
}
