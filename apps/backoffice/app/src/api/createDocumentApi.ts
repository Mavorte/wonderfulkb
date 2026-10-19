import type { Client } from "../clients/mockClients.ts";
import type { Case } from "../cases/createCase.ts";
import type { CaseValidation, DocumentRecord, DocumentResult } from "../documents/types.ts";

type Options = { basePath?: string; fetchImpl?: typeof fetch };
type WireClient = { client_id: string; name: string; ico: string; dic?: string; address?: string; status: Client["status"] };

/** API keys live in the server proxy, never in this browser client or its bundle. */
export default function createDocumentApi(options: Options = {}) {
  const basePath = options.basePath ?? "/document-api";
  const fetchImpl = options.fetchImpl ?? fetch;
  async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    const response = await fetchImpl(`${basePath}/v1${path}`, {
      method, headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error ?? `Požadavek selhal (${response.status}).`);
    }
    return response.json() as Promise<T>;
  }
  const getPath = (caseId: string, documentId?: string) =>
    `/cases/${encodeURIComponent(caseId)}/documents${documentId ? `/${encodeURIComponent(documentId)}` : ""}`;
  return {
    async getClients() {
      const clients: Client[] = [];
      let token: string | null = null;
      do {
        const response: { clients: WireClient[]; next_token: string | null } = await request(
          `/clients?status=active&limit=100${token ? `&next_token=${encodeURIComponent(token)}` : ""}`,
        );
        clients.push(...response.clients.map((c) => ({ id: c.client_id, name: c.name, ico: c.ico, dic: c.dic, address: c.address, status: c.status })));
        token = response.next_token;
      } while (token);
      return clients;
    },
    createCase(clientId: string, caseId: string, requiredDocumentTypes: string[]) {
      return request<Case>("/cases", "POST", { case_id: caseId, client_id: clientId, metadata: { required_document_types: requiredDocumentTypes } });
    },
    getCases(clientId: string) { return request<{ cases: Case[] }>(`/clients/${encodeURIComponent(clientId)}/cases`); },
    getDocuments(caseId: string) { return request<{ documents: DocumentRecord[] }>(getPath(caseId)); },
    getResult(caseId: string, documentId: string) { return request<DocumentResult>(`${getPath(caseId, documentId)}/result`); },
    getPreview(caseId: string, documentId: string, page: number) { return request<{ image_url: string }>(`${getPath(caseId, documentId)}/pages/${page}`); },
    getValidation(caseId: string) { return request<CaseValidation>(`/cases/${encodeURIComponent(caseId)}/validation`); },
    async upload(caseId: string, file: File, mode: "visual" | "auto") {
      if (file.size > 25 * 1024 * 1024 || file.size === 0) throw new Error("Soubor musí mít 1 bajt až 25 MiB.");
      const extension = file.name.split(".").pop()?.toLowerCase();
      const contentType = file.type || ({ pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg" } as Record<string, string>)[extension ?? ""];
      if (!["application/pdf", "image/png", "image/jpeg"].includes(contentType)) throw new Error("Vyberte PDF, PNG nebo JPEG.");
      const result = await request<{ document: DocumentRecord; upload: { url: string; method: string; headers: Record<string, string> } }>(getPath(caseId), "POST", {
        filename: file.name, content_type: contentType, size_bytes: file.size, mode,
      });
      const uploaded = await fetchImpl(result.upload.url, { method: result.upload.method, headers: result.upload.headers, body: file });
      if (!uploaded.ok) throw new Error("Soubor se nepodařilo nahrát. Zpracování nebylo spuštěno.");
      await request(`${getPath(caseId, result.document.document_id)}/complete`, "POST");
      return result.document.document_id;
    },
    correct(caseId: string, documentId: string, runId: string, fieldId: string, value: string | null, reason: string) {
      return request(`${getPath(caseId, documentId)}/corrections`, "POST", { run_id: runId, field_id: fieldId, normalized_value: value, reason });
    },
  };
}
export type DocumentApi = ReturnType<typeof createDocumentApi>;
