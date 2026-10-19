// Lists every client from the AWS case/client API with its cases, for the
// Clients page. The API has no list of all cases, so this pages through
// GET /clients and then reads GET /clients/{client_id}/cases per client.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, requestAwsApi, type AwsCase } from "../lib/awsApi";
import { createClientDirectory, type AwsClient, type DirectoryClient } from "./directory";

const PAGE_SIZE = 100;
// Bounds each walk at 1 000 records so the function stays well inside its timeout.
const MAX_PAGES = 10;
const CONCURRENCY = 4;

type ClientDirectoryResponse = { clients: DirectoryClient[]; truncated: boolean } | { error: "upstream" };

type Page<T> = { items: T[]; truncated: boolean };

async function listAll<T>(context: FunctionContext, path: string, key: "clients" | "cases"): Promise<Page<T>> {
  const items: T[] = [];
  let nextToken: string | null = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (nextToken) params.set("next_token", nextToken);
    const response = await requestAwsApi<Record<string, unknown>>(context, `${path}?${params}`);
    if (!response.ok || !response.body) throw new Error(`${path} returned ${response.status}`);
    items.push(...((response.body[key] as T[] | undefined) ?? []));
    const token = response.body.next_token;
    nextToken = typeof token === "string" && token ? token : null;
    if (!nextToken) return { items, truncated: false };
  }
  return { items, truncated: true };
}

async function userFunction(context: FunctionContext): Promise<ClientDirectoryResponse> {
  try {
    const clients = await listAll<AwsClient>(context, "/clients", "clients");
    const cases: AwsCase[] = [];
    let truncated = clients.truncated;
    const queue = [...clients.items];
    await Promise.all(
      Array.from({ length: CONCURRENCY }, async () => {
        for (let client = queue.shift(); client; client = queue.shift()) {
          const page = await listAll<AwsCase>(context, `/clients/${encodeURIComponent(client.client_id)}/cases`, "cases");
          cases.push(...page.items);
          truncated ||= page.truncated;
        }
      }),
    );
    return { clients: createClientDirectory(clients.items, cases), truncated };
  } catch (error) {
    console.log(`client directory request failed: ${getErrorMessage(error)}`);
  }
  context.response.setStatus(502);
  return { error: "upstream" };
}
