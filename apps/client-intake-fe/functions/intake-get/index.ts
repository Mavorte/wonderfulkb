// Resolves an intake link hash to its case and returns what the intake screen
// shows: case details, client details, and whether documents can be uploaded.
//
// Configuration (tenant-level):
// - global `kb_aws_case_api_url`: base URL of the case/client API (openapi-case-client.yaml).
//   When empty, mock data is returned so the UI can be demoed before AWS is live.
// - global `kb_aws_ingest_url`: base URL of the ingest service. Empty → upload disabled.
// - secret `aws_api_key` (type "API Key", header x-api-key): key for the case/client API.
//   It is attached by the runtime (`secretName`) and never returned to the browser.

import type { FunctionContext } from "@wonderful/types";
import type { IntakeCase, IntakeClient, IntakeData } from "../../app/src/types";
import { CASE_API_SECRET, getCaseIdForHash, getErrorMessage, getGlobalUrl } from "../shared/intakeLinks";

const TIMEOUT_MS = 8000;

// Case as returned by the case/client API. Synthetic cases carry the loan
// details as top-level fields; newer ones may put them in `metadata`.
type UpstreamCase = IntakeCase & {
  loan_agreement_no?: string;
  asset_name?: string;
  serial_number?: string;
};

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

async function getJson<T>(url: string): Promise<JsonResponse<T>> {
  const response = await fetch(url, {
    method: "GET",
    headers: { accept: "application/json" },
    secretName: CASE_API_SECRET,
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

// Maps the upstream case onto the `metadata` fields the intake screen reads.
function getPublicCase(caseData: UpstreamCase): IntakeCase {
  const metadata = caseData.metadata ?? {};
  return {
    case_id: caseData.case_id,
    client_id: caseData.client_id,
    status: caseData.status,
    created_at: caseData.created_at,
    metadata: {
      ...metadata,
      loan_number: metadata.loan_number ?? caseData.loan_agreement_no,
      asset: metadata.asset ?? caseData.asset_name,
      serial_number: metadata.serial_number ?? caseData.serial_number,
    },
  };
}

// The client is optional on the intake screen, so a failed lookup returns null
// instead of failing the whole request.
async function getClient(baseUrl: string, caseData: IntakeCase): Promise<UpstreamClient | null> {
  try {
    const byId = await getJson<UpstreamClient>(`${baseUrl}/clients/${encodeURIComponent(caseData.client_id)}`);
    if (byId.ok && byId.body) return byId.body;

    // Fallback while GET /clients/{client_id} does not exist: page through the
    // (small, synthetic) client list until the case's client turns up.
    let nextToken: string | null | undefined;
    do {
      const query = nextToken ? `?next_token=${encodeURIComponent(nextToken)}` : "";
      const list = await getJson<{ clients?: UpstreamClient[]; next_token?: string | null }>(`${baseUrl}/clients${query}`);
      if (!list.ok) return null;
      const client = list.body?.clients?.find((c) => c.client_id === caseData.client_id);
      if (client) return client;
      nextToken = list.body?.next_token;
    } while (nextToken);
    return null;
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

async function userFunction(context: FunctionContext): Promise<IntakeData | IntakeError> {
  const hash = String(context.data?.hash || "").trim();
  if (!hash) {
    context.response.setStatus(400);
    return { error: "missing_hash" };
  }

  const caseId = await getCaseIdForHash(context, hash);
  if (!caseId) {
    context.response.setStatus(404);
    return { error: "invalid_link" };
  }

  const caseApiUrl = getGlobalUrl(context, "kb_aws_case_api_url");
  const canUpload = Boolean(getGlobalUrl(context, "kb_aws_ingest_url"));

  if (!caseApiUrl) {
    const mockCase = getMockCase(caseId);
    return {
      case_id: caseId,
      is_mock: true,
      case: mockCase,
      client: getPublicClient(getMockClient(mockCase.client_id)),
      can_upload: canUpload,
    };
  }

  try {
    const caseResponse = await getJson<UpstreamCase>(`${caseApiUrl}/cases/${encodeURIComponent(caseId)}`);
    if (caseResponse.status === 404) {
      context.response.setStatus(404);
      return { error: "case_not_found" };
    }
    if (!caseResponse.ok || !caseResponse.body) {
      console.log(`case API returned ${caseResponse.status}`);
      context.response.setStatus(502);
      return { error: "upstream" };
    }
    const caseData = getPublicCase(caseResponse.body);
    const client = await getClient(caseApiUrl, caseData);
    return {
      case_id: caseId,
      is_mock: false,
      case: caseData,
      client: getPublicClient(client),
      can_upload: canUpload,
    };
  } catch (error) {
    console.log(`case API request failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }
}
