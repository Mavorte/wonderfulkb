export const CLIENTS_LIMIT = 20;

/** Client as returned by GET /clients (be-document-processing/contracts/openapi-validator-agent.yaml). */
export type UpstreamClient = {
  client_id: string;
  ico: string;
  name: string;
  status: string;
  legal_form?: string;
};

/** Client as shown in the autocomplete. */
export type ClientOption = { id: string; ico: string; name: string; status: string };

/**
 * Builds the GET /clients query string for a search text: a number is an exact
 * IČO match, anything else is a substring search over active clients' names.
 * Returns null until the text is searchable: IČO needs all eight digits, a name
 * at least two characters.
 */
export function createClientsQuery(search: string): string | null {
  const q = search.trim();
  const params = new URLSearchParams({ limit: String(CLIENTS_LIMIT) });
  if (/^\d+$/.test(q)) {
    if (q.length !== 8) return null;
    params.set("ico", q);
  } else if (q.length >= 2) {
    params.set("name", q.slice(0, 255));
    params.set("status", "active");
  } else if (q) return null;
  return params.toString();
}

export function toClientOption(client: UpstreamClient): ClientOption {
  return { id: client.client_id, ico: client.ico, name: client.name, status: client.status };
}
