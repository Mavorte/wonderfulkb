// Resolves an intake link hash to its case and returns what the intake screen
// shows: case details, client details, and where to upload documents.
//
// Configuration (tenant-level):
// - global `kb_aws_case_api_url`: base URL of the case/client API (openapi-case-client.yaml).
//   When empty, mock data is returned so the UI can be demoed before AWS is live.
// - global `kb_aws_ingest_url`: base URL of the ingest service (POST /cases/{case_id}/documents).
// - secret `kb-aws-api-key` (type "API Key", header x-api-key): key for both services.

import type { FunctionContext } from "@wonderful/types";
import type { IntakeCase, IntakeClient, IntakeData } from "../../app/src/types";

const LINKS_TABLE = "client_intake.intake_links";
const SECRET_NAME = "kb-aws-api-key";
const TIMEOUT_MS = 8000;

// Client as returned by the case/client API, before it is trimmed for the UI.
type UpstreamClient = {
  client_id: string;
  ico?: string;
  dic?: string;
  name?: string;
  legal_form?: string;
  address?: string;
  status?: string;
  contacts?: Array<{ name?: string; email?: string }>;
};

type JsonResponse<T> = { status: number; ok: boolean; body: T | null };

type IntakeError = { error: "missing_hash" | "invalid_link" | "case_not_found" | "upstream" };

function getMockCase(caseId: string): IntakeCase {
  return {
    case_id: caseId,
    client_id: "00000000-0000-4000-8000-000000000001",
    status: "open",
    created_at: "2026-10-19T09:00:00Z",
    metadata: {
      loan_number: "170170/25",
      asset: "Epiroc CC 3100 demolition shears",
      serial_number: "DGR240020",
      required_documents: [
        "Supplier tax document",
        "Purchase agreement or confirmed order",
        "Signed handover protocol",
        "Proof of VAT payment",
        "Signed guarantee",
        "Security-transfer documentation",
      ],
    },
  };
}

function getMockClient(clientId: string): UpstreamClient {
  return {
    client_id: clientId,
    ico: "04606812",
    dic: "CZ04606812",
    name: "Solom Rec s.r.o. (mock)",
    legal_form: "s.r.o.",
    address: "Mock address, Praha",
    status: "active",
    contacts: [{ name: "Mock Contact", email: "client@example.com" }],
  };
}

// Missing globals/secrets throw at runtime instead of returning null.
function getOptional<T>(read: () => T | null | undefined): T | null {
  try {
    return read() ?? null;
  } catch {
    return null;
  }
}

async function getJson<T>(url: string, apiKey: string): Promise<JsonResponse<T>> {
  const response = await fetch(url, {
    method: "GET",
    headers: { "x-api-key": apiKey, accept: "application/json" },
    timeoutMs: TIMEOUT_MS,
  });
  const text = await response.text();
  let body: T | null = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  return { status: response.status, ok: response.ok, body };
}

// The client is optional on the intake screen, so a failed lookup returns null
// instead of failing the whole request.
async function getClient(baseUrl: string, apiKey: string, caseData: IntakeCase): Promise<UpstreamClient | null> {
  try {
    const byId = await getJson<UpstreamClient>(`${baseUrl}/clients/${encodeURIComponent(caseData.client_id)}`, apiKey);
    if (byId.ok && byId.body) return byId.body;

    // Fallback while GET /clients/{client_id} does not exist: look the client up by IČO
    // stored in the case metadata.
    const ico = caseData.metadata?.ico;
    if (typeof ico !== "string" || !ico) return null;
    const byIco = await getJson<{ clients?: UpstreamClient[] }>(
      `${baseUrl}/clients?ico=${encodeURIComponent(ico)}`,
      apiKey,
    );
    return byIco.ok ? (byIco.body?.clients?.[0] ?? null) : null;
  } catch (error) {
    console.log(`client API request failed: ${getErrorMessage(error)}`);
    return null;
  }
}

function getPublicClient(client: UpstreamClient | null): IntakeClient | null {
  if (!client) return null;
  return {
    name: client.name,
    ico: client.ico,
    dic: client.dic,
    legal_form: client.legal_form,
    address: client.address,
    email: client.contacts?.find((c) => c.email)?.email ?? null,
  };
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function userFunction(context: FunctionContext): Promise<IntakeData | IntakeError> {
  const hash = String(context.data?.hash || "").trim();
  if (!hash) {
    context.response.setStatus(400);
    return { error: "missing_hash" };
  }

  const { rows } = await context.tables.filter(
    LINKS_TABLE,
    [{ column: "hash", operator: "eq", value: hash }],
    1,
    0,
  );
  const caseId: unknown = rows[0]?.data?.case_id;
  if (typeof caseId !== "string" || !caseId) {
    context.response.setStatus(404);
    return { error: "invalid_link" };
  }

  const caseApiUrl = String(getOptional(() => context.globals.get("kb_aws_case_api_url")) || "").replace(/\/+$/, "");
  const ingestUrl = String(getOptional(() => context.globals.get("kb_aws_ingest_url")) || "").replace(/\/+$/, "");
  const secret = getOptional<{ api_key?: string }>(() => context.secrets.get(SECRET_NAME));
  const apiKey = secret?.api_key ?? "";

  const upload: IntakeData["upload"] = ingestUrl
    ? { url: `${ingestUrl}/cases/${encodeURIComponent(caseId)}/documents`, api_key: apiKey }
    : null;

  if (!caseApiUrl) {
    const mockCase = getMockCase(caseId);
    return {
      case_id: caseId,
      is_mock: true,
      case: mockCase,
      client: getPublicClient(getMockClient(mockCase.client_id)),
      upload,
    };
  }

  try {
    const caseResponse = await getJson<IntakeCase>(`${caseApiUrl}/cases/${encodeURIComponent(caseId)}`, apiKey);
    if (caseResponse.status === 404) {
      context.response.setStatus(404);
      return { error: "case_not_found" };
    }
    if (!caseResponse.ok || !caseResponse.body) {
      console.log(`case API returned ${caseResponse.status}`);
      context.response.setStatus(502);
      return { error: "upstream" };
    }
    const client = await getClient(caseApiUrl, apiKey, caseResponse.body);
    return {
      case_id: caseId,
      is_mock: false,
      case: caseResponse.body,
      client: getPublicClient(client),
      upload,
    };
  } catch (error) {
    console.log(`case API request failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }
}
