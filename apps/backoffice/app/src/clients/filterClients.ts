import type { Client } from "./mockClients";

const normalize = (value: string) =>
  value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();

/** Matches clients by name or ID, ignoring case and Czech diacritics. */
export default function filterClients(clients: Client[], query: string): Client[] {
  const q = normalize(query);
  if (!q) return clients;
  return clients.filter((c) => normalize(c.name).includes(q) || normalize(c.id).includes(q));
}
