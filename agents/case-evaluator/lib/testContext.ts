// In-memory kv and tables for unit tests of lib/ and the tools' flows.

import type { Run, RunContext } from "./run";

export function createTestContext() {
  const kv = new Map<string, unknown>();
  const tables: Record<string, Array<{ id: string; data: Record<string, any> }>> = {};
  let nextId = 1;
  const ctx: RunContext = {
    kv: {
      get(key) {
        if (!kv.has(key)) throw new Error(`key not found: ${key}`);
        return kv.get(key);
      },
      set(key, value) { kv.set(key, value); },
    },
    tables: {
      async insert(table, data) {
        const id = `row-${nextId++}`;
        (tables[table] ??= []).push({ id, data: { ...data } });
        return { id };
      },
      async update(table, id, data) {
        const row = tables[table]?.find((r) => r.id === id);
        if (!row) throw new Error(`row not found: ${table}/${id}`);
        Object.assign(row.data, data);
        return row;
      },
      async filter(table, filters, limit = 100) {
        const rows = (tables[table] ?? []).filter((r) => filters.every((f) => r.data[f.column] === f.value));
        return { rows: rows.slice(0, limit) };
      },
    },
  };
  return { ctx, tables };
}

export const RUN: Run = {
  evaluation_id: "ev-test",
  row_id: "row-ev-test",
  case_id: "mock-unhappy",
  is_mock: true,
  client: {
    name: "SOLOM Rec s.r.o.",
    ico: "04606812",
    dic: "CZ04606812",
    address: "nám. Svobody 527, 739 61 Třinec - Lyžbice",
    status: "active",
    signatories: [{ name: "Jiří Labuda", function: "jednatel", authorized: true }],
    kyc: { status: "ok", checked_at: "2026-05-28" },
  },
  case_metadata: { loan_number: "170170/25", asset: "Demoliční nůžky Epiroc CC 3100 vč. příslušenství", serial_number: "DGR240020" },
  documents: [
    { document_id: "agr", title: "0_Form_Smlouva.pdf", label: "smlouva_o_uveru" },
    { document_id: "ord", title: "10_Podklady_k_vylate_objednavka.pdf", label: "objednavka" },
  ],
};
