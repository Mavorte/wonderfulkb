import assert from "node:assert/strict";
import { describe, it } from "node:test";
import filterClients from "./filterClients.ts";
import { mockClients } from "./mockClients.ts";

describe("filterClients", () => {
  it("returns all clients for an empty query", () => {
    assert.equal(filterClients(mockClients, "  ").length, mockClients.length);
  });

  it("ignores case and diacritics", () => {
    assert.deepEqual(filterClients(mockClients, "obrabeni").map((c) => c.name), ["Dravonex Obrábění s.r.o."]);
    assert.deepEqual(filterClients(mockClients, "VŘESAVA").map((c) => c.name), ["Agroluh Vřesava s.r.o."]);
  });

  it("matches by client ID", () => {
    assert.deepEqual(filterClients(mockClients, "98007106").map((c) => c.id), [mockClients[1].id]);
  });
});
