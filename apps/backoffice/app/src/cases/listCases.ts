import type { useWonderful } from "@wonderful/app-sdk";

export type CaseSummary = {
  id: string;
  clientId: string;
  clientName: string | null;
  clientIco: string | null;
  status: string;
  createdAt: string;
};

export type CasePage = { cases: CaseSummary[]; nextToken: string | null };

type Api = ReturnType<typeof useWonderful>["api"];

export type CaseSummaryResponse = {
  case_id: string;
  client_id: string;
  client_name: string | null;
  client_ico: string | null;
  status: string;
  created_at: string;
};

type CaseListResponse =
  | { cases: CaseSummaryResponse[]; next_token: string | null; error?: undefined }
  | { error: string };

export function toCaseSummary(c: CaseSummaryResponse): CaseSummary {
  return {
    id: c.case_id,
    clientId: c.client_id,
    clientName: c.client_name,
    clientIco: c.client_ico,
    status: c.status,
    createdAt: c.created_at,
  };
}

/** Lists one page of all cases from the AWS case/client API, newest first. */
export default async function listCases(api: Api, nextToken?: string | null): Promise<CasePage> {
  const result = await api.invokeFunction<CaseListResponse>("backoffice/case-list", {
    method: "GET",
    params: nextToken ? { next_token: nextToken } : undefined,
  });
  if (result.error !== undefined) throw new Error(result.error);
  return { cases: result.cases.map(toCaseSummary), nextToken: result.next_token };
}
