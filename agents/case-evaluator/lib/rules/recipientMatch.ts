import { type Run, findDocument } from "../run";
import { type CheckOutcome, rejected, requireReasoning } from "./check";

export type RecipientMatchInput = {
  status: "passed" | "conflict" | "cannot_verify";
  agreement_name?: string;
  agreement_ico?: string;
  document_id?: string;
  page?: number;
  reasoning: string;
};

// Ignores case, spacing and legal-form punctuation ("s. r. o." = "s.r.o." = "sro").
export function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[.,]/g, "").replace(/\s+/g, "");
}

export function normalizeIco(ico: string): string {
  return ico.replace(/\s+/g, "");
}

export function checkRecipientMatch(run: Run, input: RecipientMatchInput): CheckOutcome {
  const problems: string[] = [];
  requireReasoning(input.reasoning, problems);
  const client = run.client;
  const name = input.agreement_name?.trim() ?? "";
  const ico = input.agreement_ico?.trim() ?? "";
  const document = input.document_id ? findDocument(run, input.document_id) : undefined;
  if (input.document_id && !document) problems.push(`document_id "${input.document_id}" is not a document of this case.`);

  if (input.status === "cannot_verify") {
    if (client && name && ico) {
      problems.push("status cannot_verify, but the client record and both agreement values are there; compare them and use passed or conflict.");
    }
  } else {
    if (!client) problems.push("There is no client record, so use status cannot_verify.");
    if (!name || !ico) problems.push("Give agreement_name and agreement_ico as written in the agreement.");
    if (!document) problems.push("Give the document_id (and page) of the agreement you read the values from.");
  }

  const nameMatches = client && name ? normalizeName(name) === normalizeName(client.name) : false;
  const icoMatches = client && ico ? normalizeIco(ico) === normalizeIco(client.ico) : false;
  if (client && name && ico) {
    if (input.status === "passed" && !(nameMatches && icoMatches)) {
      const diffs = [!nameMatches && `name "${name}" vs client "${client.name}"`, !icoMatches && `IČO "${ico}" vs client "${client.ico}"`];
      problems.push(`status passed, but the values differ: ${diffs.filter(Boolean).join("; ")}. Use conflict.`);
    }
    if (input.status === "conflict" && nameMatches && icoMatches) {
      problems.push("status conflict, but the name and IČO match the client record. Use passed.");
    }
  }
  if (problems.length) return rejected(problems);

  return {
    result: {
      rule_id: "recipient_matches_client",
      status: input.status,
      expected: client ? `${client.name}, IČO ${client.ico}` : "Client record",
      found: name || ico ? `${name || "?"}, IČO ${ico || "?"}` : "Recipient not readable in the agreement",
      sources: document ? [{ document_id: document.document_id, title: document.title, page: input.page }] : [],
      details: { name_matches: nameMatches, ico_matches: icoMatches },
      reasoning: input.reasoning,
    },
  };
}
