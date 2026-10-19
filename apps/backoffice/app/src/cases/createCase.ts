import createDocumentApi from "../api/createDocumentApi.ts";
import type { WonderfulAPI } from "@wonderful/app-sdk";
import type { Client } from "../clients/mockClients.ts";

export type Case = { case_id: string; client_id: string; status: "open"; created_at: string; metadata?: Record<string, unknown>; hash?: string };
export type CaseCreation = { case: Case; intakeError?: string };

type CaseCreateResponse =
  | { case_id: string; client_id: string; hash: string; created_at: string; error?: undefined }
  | { error: string };

/** Persist the OCR case, then register the Client Intake link against the same ID. */
export default async function createCase(
  client: Client,
  caseId: string,
  requiredDocumentTypes: string[],
  documentApi = createDocumentApi(),
  intakeApi?: Pick<WonderfulAPI, "invokeFunction">,
): Promise<CaseCreation> {
  const created = await documentApi.createCase(client.id, caseId, requiredDocumentTypes);
  if (!intakeApi) return { case: created };
  try {
    const link = await intakeApi.invokeFunction<CaseCreateResponse>("backoffice/case-create", {
      method: "POST",
      params: { client_id: created.client_id, case_id: created.case_id },
    });
    if (link.error !== undefined) throw new Error(link.error);
    if (link.case_id !== created.case_id || link.client_id !== created.client_id || !link.hash) {
      throw new Error("INTAKE_CASE_MISMATCH");
    }
    return { case: { ...created, hash: link.hash } };
  } catch (error) {
    // Case creation already succeeded. Keep its documents accessible and let the
    // caller retry link registration with this same case ID.
    return { case: created, intakeError: error instanceof Error ? error.message : "INTAKE_REGISTRATION_FAILED" };
  }
}
