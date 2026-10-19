import type { useWonderful } from "@wonderful/app-sdk";

export type Client = { id: string; ico: string; name: string; status: string };

type Api = ReturnType<typeof useWonderful>["api"];

type ClientsListResponse = { clients: Client[]; error?: undefined } | { error: string };

/** Searches clients by IČO (a number) or name through the AWS case/client API. */
export default async function searchClients(api: Api, query: string): Promise<Client[]> {
  const result = await api.invokeFunction<ClientsListResponse>("backoffice/clients-list", {
    method: "POST",
    params: { q: query },
  });
  if (result.error !== undefined) throw new Error(result.error);
  return result.clients;
}
