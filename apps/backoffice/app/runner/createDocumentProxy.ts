import type { IncomingMessage, ServerResponse } from "node:http";

type Options = { documentApiUrl: string; caseClientApiUrl?: string; documentApiKey?: string; caseClientApiKey?: string };

export default function createDocumentProxy(options: Options) {
  return async function proxy(request: IncomingMessage, response: ServerResponse, url: URL) {
    const path = url.pathname.replace(/^\/document-api/, "");
    if (!/^\/v1\/(clients|cases)(\/|$)/.test(path)) {
      response.writeHead(404, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "NOT_FOUND" }));
      return;
    }
    const caseClient = /^\/v1\/clients(?:\/|$)/.test(path) || /^\/v1\/cases(?:\/[^/]+)?$/.test(path);
    const base = caseClient ? options.caseClientApiUrl ?? options.documentApiUrl : options.documentApiUrl;
    const key = caseClient ? options.caseClientApiKey ?? options.documentApiKey : options.documentApiKey;
    const target = new URL(path + url.search, base);
    const headers = new Headers();
    if (key) headers.set("x-api-key", key);
    if (request.headers["content-type"]) headers.set("Content-Type", request.headers["content-type"]);
    const method = request.method ?? "GET";
    try {
      const upstream = await fetch(target, {
        method, headers,
        body: ["GET", "HEAD"].includes(method) ? undefined : request as unknown as BodyInit,
        ...(!["GET", "HEAD"].includes(method) ? { duplex: "half" } : {}),
        signal: AbortSignal.timeout(35_000),
      });
      response.writeHead(upstream.status, { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" });
      response.end(Buffer.from(await upstream.arrayBuffer()));
    } catch {
      response.writeHead(502, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "DOCUMENT_API_UNAVAILABLE" }));
    }
  };
}
