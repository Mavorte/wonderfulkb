// Resolves an intake link hash to its case and returns what the intake screen
// shows: case details, client details, and where to upload documents.
//
// Configuration (tenant-level):
// - global `kb_aws_case_api_url`: base URL of the case/client API (openapi-case-client.yaml).
//   When empty, mock data is returned so the UI can be demoed before AWS is live.
// - global `kb_aws_ingest_url`: base URL of the ingest service (POST /cases/{case_id}/documents).
// - secret `kb-aws-api-key` (type "API Key", header x-api-key): key for both services.

const LINKS_TABLE = "client_intake.intake_links";
const SECRET_NAME = "kb-aws-api-key";
const TIMEOUT_MS = 8000;

function getMockCase(caseId) {
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

function getMockClient(clientId) {
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
function getOptional(read) {
  try {
    return read() ?? null;
  } catch {
    return null;
  }
}

async function getJson(url, apiKey) {
  const response = await fetch(url, {
    method: "GET",
    headers: { "x-api-key": apiKey, accept: "application/json" },
    timeoutMs: TIMEOUT_MS,
  });
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  return { status: response.status, ok: response.ok, body };
}

async function getClient(baseUrl, apiKey, caseData) {
  const byId = await getJson(`${baseUrl}/clients/${encodeURIComponent(caseData.client_id)}`, apiKey);
  if (byId.ok && byId.body) return byId.body;

  // Fallback while GET /clients/{client_id} does not exist: look the client up by IČO
  // stored in the case metadata.
  const ico = caseData.metadata?.ico;
  if (!ico) return null;
  const byIco = await getJson(`${baseUrl}/clients?ico=${encodeURIComponent(ico)}`, apiKey);
  return byIco.ok ? (byIco.body?.clients?.[0] ?? null) : null;
}

function getPublicClient(client) {
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

async function userFunction(context) {
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
  const caseId = rows[0]?.data?.case_id;
  if (!caseId) {
    context.response.setStatus(404);
    return { error: "invalid_link" };
  }

  const caseApiUrl = String(getOptional(() => context.globals.get("kb_aws_case_api_url")) || "").replace(/\/+$/, "");
  const ingestUrl = String(getOptional(() => context.globals.get("kb_aws_ingest_url")) || "").replace(/\/+$/, "");
  const secret = getOptional(() => context.secrets.get(SECRET_NAME));
  const apiKey = secret?.api_key ?? "";

  const upload = ingestUrl
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
    const caseResponse = await getJson(`${caseApiUrl}/cases/${encodeURIComponent(caseId)}`, apiKey);
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
    console.log(`case API request failed: ${error.message}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }
}
