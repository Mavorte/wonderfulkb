// Creates a case for a client and registers its intake link, so the Client
// Intake app can resolve `?h=<hash>` to the case.
//
// Mocked until the AWS case/client API is integrated: the case id and hash are
// generated here and nothing is sent to AWS.

import { generateCaseId, generateHash } from "./ids";

const LINKS_TABLE = "client_intake.intake_links";

async function userFunction(context) {
  const clientId = String(context.data?.client_id || "").trim();
  if (!clientId) {
    context.response.setStatus(400);
    return { error: "missing_client_id" };
  }

  const caseId = generateCaseId();
  const hash = generateHash();
  const insertedAt = Date.now();
  await context.tables.insert(LINKS_TABLE, { hash, case_id: caseId, inserted_at: insertedAt });

  return {
    case_id: caseId,
    client_id: clientId,
    hash,
    created_at: new Date(insertedAt).toISOString(),
  };
}
