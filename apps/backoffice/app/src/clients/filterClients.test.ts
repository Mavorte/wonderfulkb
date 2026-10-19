import assert from "node:assert/strict";
import { describe, it } from "node:test";
import filterClients from "./filterClients.ts";
import { mockClients } from "./mockClients.ts";

describe("filterClients", () => {
  it("returns all clients for an empty query", () => {
    assert.equal(filterClients(mockClients, "  ").length, mockClients.length);
  });

  it("ignores case and diacritics", () => {
    assert.deepEqual(filterClients(mockClients, "dvorak").map((c) => c.name), ["Lucie Dvořáková"]);
    assert.deepEqual(filterClients(mockClients, "ČERNÝ").map((c) => c.name), ["Tomáš Černý"]);
  });

  it("matches by client ID", () => {
    assert.deepEqual(filterClients(mockClients, "cl-1026").map((c) => c.id), ["CL-102611"]);
  });
});
