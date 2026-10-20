// Request correction (body: case_id, findings [{ label, found }], note): leaves
// what the client must fix in backoffice.correction_calls, then has the
// correction-caller agent call the client. The agent picks the row up by the
// number it dials, verifies the surname stored here and emails the findings with
// the upload link (mocked).
//
// Configuration (globals):
// - `correction_call_destination`: the number to call and text (demo: one number for every case).
// - `correction_call_from_number`: the caller ID attached to the correction-caller agent.
// - `public_access_base_url`: the Client Intake base URL of the upload link.
// Placing the call uses context.api, so the Function needs a service account
// that may start outbound calls (agents:edit).

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage } from "../lib/awsApi.ts";
import { buildIntakeLink, generateHash } from "../case-create/ids.ts";

const CALLS_TABLE = "backoffice.correction_calls";
const LINKS_TABLE = "client_intake.intake_links";
const CASE_FUNCTION = "agent-functions/eval-case-get";
const MAX_FINDINGS = 20;
const MAX_TEXT = 500;

type Finding = { label: string; found: string | null };

type EvalCase = {
  case?: { metadata?: { client_name?: string } };
  client?: { name?: string; signatories?: { name?: string }[] } | null;
  error?: string;
};

export type CorrectionCallResponse =
  | { request_id: string; status: "calling"; phone_number: string; communication_id: string | null }
  | {
      error: "bad_request" | "not_configured" | "case_not_found" | "no_contact" | "no_upload_link" | "call_failed";
      message?: string;
    };

function getText(value: unknown, max = MAX_TEXT): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

export function parseFindings(raw: unknown): Finding[] | null {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > MAX_FINDINGS) return null;
  const findings = raw.map((f) => ({ label: getText(f?.label, 200), found: getText(f?.found) || null }));
  return findings.every((f) => f.label) ? findings : null;
}

/** The surname of the client's first signatory, the person the agent talks to. */
export function getContactLastName(evalCase: EvalCase): string | null {
  const parts = getText(evalCase.client?.signatories?.[0]?.name).split(/\s+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : null;
}

// The client keeps using the intake link the case already has; a case without one gets a new one.
async function getUploadLink(context: FunctionContext, caseId: string): Promise<string | null> {
  const baseUrl = String(context.globals.get("public_access_base_url") ?? "");
  const { rows } = await context.tables.filter(LINKS_TABLE, [{ column: "case_id", operator: "eq", value: caseId }], 1, 0, [
    { column: "inserted_at", direction: "desc" },
  ]);
  let hash = rows[0]?.data?.hash ? String(rows[0].data.hash) : null;
  if (!hash) {
    hash = generateHash();
    await context.tables.insert(LINKS_TABLE, { hash, case_id: caseId, inserted_at: Date.now() });
  }
  return buildIntakeLink(baseUrl, hash);
}

export async function userFunction(context: FunctionContext): Promise<CorrectionCallResponse> {
  const caseId = getText(context.data?.case_id, 200);
  const findings = parseFindings(context.data?.findings);
  if (!caseId || !findings) {
    context.response.setStatus(400);
    return { error: "bad_request" };
  }
  const note = getText(context.data?.note, 1000);

  const to = String(context.globals.get("correction_call_destination") ?? "").trim();
  const from = String(context.globals.get("correction_call_from_number") ?? "").trim();
  if (!to || !from) {
    context.response.setStatus(500);
    return { error: "not_configured", message: "Set the globals correction_call_destination and correction_call_from_number." };
  }

  let evalCase: EvalCase;
  try {
    evalCase = (await context.functions.run({ slug: CASE_FUNCTION, params: { case_id: caseId } })).result as EvalCase;
  } catch (error) {
    evalCase = { error: getErrorMessage(error) };
  }
  if (evalCase.error) {
    context.response.setStatus(evalCase.error === "case_not_found" ? 404 : 502);
    return { error: evalCase.error === "case_not_found" ? "case_not_found" : "call_failed", message: evalCase.error };
  }
  const lastName = getContactLastName(evalCase);
  if (!lastName) {
    context.response.setStatus(409);
    return { error: "no_contact", message: "The client has no signatory on file to verify." };
  }
  const uploadLink = await getUploadLink(context, caseId);
  if (!uploadLink) {
    context.response.setStatus(500);
    return { error: "no_upload_link", message: "Set the global public_access_base_url." };
  }

  const requestId = generateHash();
  const companyName = getText(evalCase.client?.name) || getText(evalCase.case?.metadata?.client_name);
  const row = await context.tables.insert(CALLS_TABLE, {
    request_id: requestId,
    case_id: caseId,
    phone_number: to,
    company_name: companyName,
    contact_last_name: lastName,
    findings: JSON.stringify(findings),
    note,
    upload_link: uploadLink,
    status: "pending",
    requested_by: getText(context.metadata?.user?.email) || getText(context.metadata?.user?.id),
    requested_at: new Date().toISOString(),
  });

  try {
    const response = await context.api.post("/v1/agents/outbound", {
      body: { from, to, call_purpose: `Request corrections for case ${caseId}${companyName ? ` (${companyName})` : ""}.` },
    });
    const communicationId = response?.communication_id ?? response?.id ?? null;
    return { request_id: requestId, status: "calling", phone_number: to, communication_id: communicationId };
  } catch (error) {
    console.log(`outbound call for case ${caseId} failed: ${getErrorMessage(error)}`);
    await context.tables.update(CALLS_TABLE, row.id, { status: "call_failed" });
    context.response.setStatus(502);
    return { error: "call_failed", message: getErrorMessage(error) };
  }
}
