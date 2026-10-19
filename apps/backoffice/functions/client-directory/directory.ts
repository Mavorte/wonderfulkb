import type { AwsCase } from "../lib/awsApi";

/** Client as returned by GET /clients (openapi-case-client.yaml). */
export type AwsClient = {
  client_id: string;
  ico: string;
  name: string;
  status: string;
  dic?: string;
  legal_form?: string;
  address?: string;
  contacts?: { email?: string }[];
  signatories?: { name?: string; function?: string }[];
  kyc?: { status?: string; checked_at?: string };
};

export type DirectoryCase = {
  case_id: string;
  status: string;
  created_at: string;
  asset: string | null;
  principal: number | null;
};

export type DirectoryClient = {
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
  cases: DirectoryCase[];
};

function getString(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function getNumber(value: unknown): number | null {
  const n = typeof value === "number" ? value : typeof value === "string" && value ? Number(value) : NaN;
  return Number.isFinite(n) ? n : null;
}

// Timestamps arrive as `...Z` or `...+00:00`, with or without milliseconds, so
// order by the parsed instant; an unparsable one sorts last.
function getTime(iso: string): number {
  const time = Date.parse(iso);
  return Number.isNaN(time) ? -Infinity : time;
}

function toDirectoryCase(awsCase: AwsCase): DirectoryCase {
  const metadata = awsCase.metadata ?? {};
  const asset =
    [getString(metadata.brand), getString(metadata.model)].filter(Boolean).join(" ") || getString(metadata.asset_name);
  return {
    case_id: awsCase.case_id,
    status: awsCase.status,
    created_at: awsCase.created_at,
    asset,
    principal: getNumber(metadata.principal),
  };
}

/** Joins cases to their clients, clients by name and each client's cases newest first. */
export function createClientDirectory(clients: AwsClient[], cases: AwsCase[]): DirectoryClient[] {
  const casesByClient = new Map<string, DirectoryCase[]>();
  for (const awsCase of cases) {
    const list = casesByClient.get(awsCase.client_id) ?? [];
    list.push(toDirectoryCase(awsCase));
    casesByClient.set(awsCase.client_id, list);
  }
  return clients
    .map((client) => {
      const signatory = client.signatories?.[0];
      return {
        client_id: client.client_id,
        name: client.name,
        ico: client.ico,
        dic: getString(client.dic),
        legal_form: getString(client.legal_form),
        address: getString(client.address),
        status: client.status,
        kyc_status: getString(client.kyc?.status),
        kyc_checked_at: getString(client.kyc?.checked_at),
        signatory: signatory?.name ? { name: signatory.name, function: signatory.function ?? "" } : null,
        email: getString(client.contacts?.find((c) => c.email)?.email),
        cases: (casesByClient.get(client.client_id) ?? []).sort((a, b) => getTime(b.created_at) - getTime(a.created_at)),
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name, "cs"));
}
