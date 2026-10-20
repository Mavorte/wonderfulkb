// The correction request the back office leaves for this call. The backoffice
// app's correction-call Function writes one row per call it places, keyed by the
// number it dials; the tools read and advance that row during the call.

export const REQUESTS_TABLE = "backoffice.correction_calls";
export const MAX_ATTEMPTS = 3;

const KV_KEY = "correction_request";

export type Finding = { label: string; found: string | null };

export type RequestRow = {
  request_id: string;
  case_id: string;
  phone_number: string;
  company_name: string;
  contact_last_name: string;
  findings: string;
  note: string;
  upload_link: string;
  status: string;
};

/** What this call knows about its request; kept in the session KV between tool calls. */
export type CallState = {
  row_id: string;
  request_id: string;
  verified: boolean;
  attempts: number;
  sms_sent: boolean;
};

type Ctx = {
  kv: { get(key: string): any; set(key: string, value: any): any };
  tables: {
    filter(table: string, filters: { column: string; operator: string; value: unknown }[], limit?: number, offset?: number, orderBy?: { column: string; direction: "asc" | "desc" }[]): Promise<{ rows: { id: string; data: Record<string, any> }[] }>;
    getRow(table: string, rowId: string): Promise<{ id: string; data: Record<string, any> } | null>;
    update(table: string, rowId: string, data: Record<string, any>): Promise<unknown>;
  };
};

export function getState(ctx: Ctx): CallState | null {
  return (ctx.kv.get(KV_KEY) as CallState | null) ?? null;
}

export function setState(ctx: Ctx, state: CallState): void {
  ctx.kv.set(KV_KEY, state);
}

/** The newest pending request for the dialed number. */
export async function findPending(ctx: Ctx, phoneNumber: string): Promise<{ id: string; data: RequestRow } | null> {
  const { rows } = await ctx.tables.filter(
    REQUESTS_TABLE,
    [
      { column: "phone_number", operator: "eq", value: phoneNumber },
      { column: "status", operator: "eq", value: "pending" },
    ],
    1,
    0,
    [{ column: "requested_at", direction: "desc" }],
  );
  const row = rows[0];
  return row ? { id: row.id, data: row.data as RequestRow } : null;
}

export async function loadRow(ctx: Ctx, state: CallState): Promise<RequestRow | null> {
  const row = await ctx.tables.getRow(REQUESTS_TABLE, state.row_id);
  return row ? (row.data as RequestRow) : null;
}

export async function updateRow(ctx: Ctx, state: CallState, data: Record<string, unknown>): Promise<void> {
  await ctx.tables.update(REQUESTS_TABLE, state.row_id, data);
}

export function parseFindings(raw: string): Finding[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.filter((f) => f && typeof f.label === "string") : [];
  } catch {
    return [];
  }
}

// The agent runtime has no String.prototype.normalize, so fold the accented
// letters of Czech, Slovak and German names by hand.
const FOLD: Record<string, string> = {
  á: "a", ä: "a", č: "c", ď: "d", é: "e", ě: "e", í: "i", ĺ: "l", ľ: "l", ň: "n",
  ó: "o", ô: "o", ö: "o", ŕ: "r", ř: "r", š: "s", ß: "ss", ť: "t", ú: "u", ů: "u", ü: "u", ý: "y", ž: "z",
};

// Speech-to-text drops or swaps diacritics and case, so compare the bare letters.
export function normalizeName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z]/g, (ch) => FOLD[ch] ?? "");
}

/**
 * The caller may say their full name, so the surname on file may be the whole
 * answer or its last word. Longer answers are refused, so one attempt cannot
 * try a list of surnames.
 */
export function lastNameMatches(spoken: string, onFile: string): boolean {
  const expected = normalizeName(onFile);
  const words = spoken.trim().split(/\s+/);
  if (!expected || words.length > 2) return false;
  return normalizeName(spoken) === expected || normalizeName(words[words.length - 1]) === expected;
}
