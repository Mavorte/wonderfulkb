import { generateCaseId, generateHash } from "./ids.ts";

type Context = {
  data?: { client_id?: unknown; case_id?: unknown };
  response: { setStatus(status: number): void };
  tables: {
    filter(table: string, filters: { column: string; operator: string; value: string }[], limit: number, offset: number): Promise<{ rows: { data?: Record<string, unknown> }[] }>;
    insert(table: string, data: Record<string, unknown>): Promise<unknown>;
  };
};

const LINKS_TABLE = "client_intake.intake_links";

/** Register the supplied backend case, retaining the original standalone mock mode. */
export default async function createCaseLink(context: Context) {
  const clientId = String(context.data?.client_id || "").trim();
  if (!clientId) {
    context.response.setStatus(400);
    return { error: "missing_client_id" };
  }
  const suppliedCaseId = context.data?.case_id;
  if (suppliedCaseId !== undefined && (typeof suppliedCaseId !== "string" || !/^[A-Za-z0-9._-]{1,128}$/.test(suppliedCaseId))) {
    context.response.setStatus(400);
    return { error: "invalid_case_id" };
  }
  const caseId = suppliedCaseId ?? generateCaseId();
  if (suppliedCaseId) {
    const { rows } = await context.tables.filter(LINKS_TABLE, [{ column: "case_id", operator: "eq", value: caseId }], 1, 0);
    const existing = rows[0]?.data;
    if (typeof existing?.hash === "string" && existing.hash) {
      const insertedAt = typeof existing.inserted_at === "number" && Number.isFinite(existing.inserted_at)
        ? existing.inserted_at : Date.now();
      return { case_id: caseId, client_id: clientId, hash: existing.hash, created_at: new Date(insertedAt).toISOString() };
    }
  }
  const hash = generateHash();
  const insertedAt = Date.now();
  await context.tables.insert(LINKS_TABLE, { hash, case_id: caseId, inserted_at: insertedAt });
  return { case_id: caseId, client_id: clientId, hash, created_at: new Date(insertedAt).toISOString() };
}
