import type { useWonderful } from "@wonderful/app-sdk";

export type DirectoryCase = {
  id: string;
  status: string;
  createdAt: string;
  asset: string | null;
  principal: number | null;
};

export type DirectoryClient = {
  id: string;
  name: string;
  ico: string;
  dic: string | null;
  legalForm: string | null;
  address: string | null;
  status: string;
  kycStatus: string | null;
  kycCheckedAt: string | null;
  signatory: { name: string; function: string } | null;
  email: string | null;
  cases: DirectoryCase[];
};

export type ClientDirectory = { clients: DirectoryClient[]; truncated: boolean };

type Api = ReturnType<typeof useWonderful>["api"];

type DirectoryClientResponse = {
  client_id: string;
  name: string;
  ico: string;
  dic: string | null;
  legal_form: string | null;
  address: string | null;
  status: string;
  kyc_status: string | null;
  kyc_checked_at: string | null;
  signatory: { name: string; function: string } | null;
  email: string | null;
  cases: { case_id: string; status: string; created_at: string; asset: string | null; principal: number | null }[];
};

type ClientDirectoryResponse =
  | { clients: DirectoryClientResponse[]; truncated: boolean; error?: undefined }
  | { error: string };

function toDirectoryClient(c: DirectoryClientResponse): DirectoryClient {
  return {
    id: c.client_id,
    name: c.name,
    ico: c.ico,
    dic: c.dic,
    legalForm: c.legal_form,
    address: c.address,
    status: c.status,
    kycStatus: c.kyc_status,
    kycCheckedAt: c.kyc_checked_at,
    signatory: c.signatory,
    email: c.email,
    cases: c.cases.map((k) => ({
      id: k.case_id,
      status: k.status,
      createdAt: k.created_at,
      asset: k.asset,
      principal: k.principal,
    })),
  };
}

/** Lists every client with its cases from the AWS case/client API, sorted by name. */
export default async function listClientDirectory(api: Api): Promise<ClientDirectory> {
  const result = await api.invokeFunction<ClientDirectoryResponse>("backoffice/client-directory", { method: "GET" });
  if (result.error !== undefined) throw new Error(result.error);
  return { clients: result.clients.map(toDirectoryClient), truncated: result.truncated };
}
