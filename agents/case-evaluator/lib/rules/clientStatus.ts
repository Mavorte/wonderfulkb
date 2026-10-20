// client_status_valid: the client is active with valid KYC (client record),
// and the people who sign for the recipient in the documents are among its
// authorized signatories.

import { type DocumentRead, type Run, type Source, findDocument } from "../run";
import { type CheckOutcome, rejected, requireReasoning } from "./check";
import { stripDiacritics } from "./consistency";

export type ClientStatusInput = {
  status: "passed" | "conflict" | "cannot_verify";
  signatories: Array<{ name: string; document_id: string; page?: number }>;
  reasoning: string;
};

const TITLES = new Set(["ing", "mgr", "bc", "judr", "mudr", "phdr", "rndr", "phd", "mba", "csc", "dipl"]);

// Ignores case, diacritics, academic titles and name order ("Ing. Jiří Labuda" = "Labuda Jiri").
export function normalizePerson(name: string): string {
  return stripDiacritics(name.toLowerCase())
    .split(/[\s,.]+/)
    .filter((t) => t && !TITLES.has(t))
    .sort()
    .join(" ");
}

export function checkClientStatus(run: Run, getRead: (documentId: string) => DocumentRead | null, input: ClientStatusInput): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  const client = run.client;
  for (const s of input.signatories) {
    const document = findDocument(run, s.document_id);
    const at = `Signatory "${s.name}"`;
    if (!s.name.trim()) problems.push("Each signatory needs a name.");
    if (!document) {
      problems.push(`${at}: document_id "${s.document_id}" is not a document of this case.`);
      continue;
    }
    const read = getRead(document.document_id);
    if (!read) problems.push(`${at}: read ${document.title} with get_document first.`);
    if (s.page === undefined) problems.push(`${at}: give the page the name is on.`);
    else if (read && (s.page < 1 || s.page > read.page_count)) problems.push(`${at}: page ${s.page} is not a page of ${document.title} (1-${read.page_count}).`);
    else if (read?.empty_pages.includes(s.page)) problems.push(`${at}: page ${s.page} has no text, so the name can't come from it.`);
  }
  if (problems.length) return rejected(problems);

  if (!client) {
    if (input.status !== "cannot_verify") return rejected(["There is no client record, so use status cannot_verify."]);
    return {
      result: {
        rule_id: "client_status_valid",
        status: "cannot_verify",
        expected: "Active client with KYC ok, signed by its authorized signatories",
        found: "No client record",
        sources: [],
        reasoning: input.reasoning,
      },
    };
  }

  const authorized = (client.signatories ?? []).filter((s) => s.authorized !== false);
  const authorizedNames = new Set(authorized.map((s) => normalizePerson(s.name)));
  const names = [...new Set(input.signatories.map((s) => s.name.trim()))];
  const unauthorized = names.filter((n) => !authorizedNames.has(normalizePerson(n)));
  const issues = [
    client.status !== "active" && `client status is "${client.status}", not active`,
    client.kyc?.status !== "ok" && `KYC status is "${client.kyc?.status ?? "unknown"}", not ok`,
    ...unauthorized.map((n) => `${n} signs for the recipient but is not an authorized signatory`),
  ].filter((i): i is string => Boolean(i));

  if (input.status === "passed") {
    if (issues.length) problems.push(`status passed, but: ${issues.join("; ")}. Use conflict.`);
    else if (!names.length) problems.push("status passed needs the names of the people who sign for the recipient. If no document shows them, use cannot_verify.");
  }
  if (input.status === "conflict" && !issues.length) {
    problems.push("status conflict, but the client is active, KYC is ok and every signatory is authorized. Use passed.");
  }
  if (input.status === "cannot_verify") {
    if (issues.length) problems.push(`status cannot_verify, but: ${issues.join("; ")}. Use conflict.`);
    else if (names.length) problems.push("status cannot_verify, but the client record and the signatories are there to compare. Use passed or conflict.");
  }
  if (problems.length) return rejected(problems);

  // Each signatory's name where it was read, in a signature or party block.
  const sources: Source[] = input.signatories.map((s) => {
    const document = findDocument(run, s.document_id)!;
    return {
      document_id: document.document_id,
      title: document.title,
      page: s.page,
      role: "evidence",
      field: "signatory",
      ...(unauthorized.includes(s.name.trim()) && { issue: "unauthorized signatory" }),
      locate: { value: s.name.trim(), labels: ["podpisovy_blok", "smluvni_strana"], parties: ["borrower", "buyer"] },
    };
  });
  return {
    result: {
      rule_id: "client_status_valid",
      status: input.status,
      expected: `Active client with KYC ok; signed by ${authorized.map((s) => s.name).join(", ") || "an authorized signatory"} (client record)`,
      found: issues.length
        ? issues.join("; ")
        : names.length ? `Active, KYC ok, signed by ${names.join(", ")}` : "Active, KYC ok; no signatory names in the documents",
      sources,
      details: {
        client_status: client.status,
        kyc: client.kyc ?? null,
        authorized_signatories: authorized.map((s) => s.name),
        signatories: input.signatories.map((s) => ({ ...s, document_id: findDocument(run, s.document_id)!.document_id, authorized: authorizedNames.has(normalizePerson(s.name)) })),
      },
      reasoning: input.reasoning,
    },
  };
}
