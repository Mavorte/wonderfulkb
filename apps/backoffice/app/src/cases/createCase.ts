import type { Client } from "../clients/mockClients";

export type Case = { id: string; clientId: string; createdAt: string };

let nextNumber = 1042;

/** Mocked: simulates a network round trip and returns a new case. Nothing is persisted. */
export default async function createCase(client: Client): Promise<Case> {
  await new Promise((resolve) => setTimeout(resolve, 700));
  return { id: `CASE-${nextNumber++}`, clientId: client.id, createdAt: new Date().toISOString() };
}
