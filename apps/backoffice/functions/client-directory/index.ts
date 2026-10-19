// Lists every client from the AWS case/client API with its cases, for the
// Clients page. The API has no list of all cases, so this pages through
// GET /clients and then reads GET /clients/{client_id}/cases per client.

import type { FunctionContext } from "@wonderful/types";
import { getErrorMessage, listAll, type AwsCase } from "../lib/awsApi";
import { createClientDirectory, type AwsClient, type DirectoryClient } from "./directory";

const CONCURRENCY = 4;

type ClientDirectoryResponse = { clients: DirectoryClient[]; truncated: boolean } | { error: "upstream" };

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
