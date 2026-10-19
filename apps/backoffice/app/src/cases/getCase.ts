import type { useWonderful } from "@wonderful/app-sdk";
import { toCaseSummary, type CaseSummary, type CaseSummaryResponse } from "./listCases";

export type CaseDetail = CaseSummary & { hash: string | null; metadata: Record<string, unknown> };

type Api = ReturnType<typeof useWonderful>["api"];

type CaseGetResponse =
  | { case: CaseSummaryResponse & { metadata: Record<string, unknown> }; hash: string | null; error?: undefined }
  | { error: string };

/** Looks up one case by its ID; throws `case_not_found` when it does not exist. */
export default async function getCase(api: Api, caseId: string): Promise<CaseDetail> {
  const result = await api.invokeFunction<CaseGetResponse>("backoffice/case-get", {
    method: "GET",
    params: { case_id: caseId },
  });
  if (result.error !== undefined) throw new Error(result.error);
  return { ...toCaseSummary(result.case), hash: result.hash, metadata: result.case.metadata };
}
