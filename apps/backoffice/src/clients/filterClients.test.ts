import { describe, expect, it } from "vitest";
import { filterClients } from "./filterClients";
import { mockClients } from "./mockClients";

describe("filterClients", () => {
  it("returns all clients for an empty query", () => {
    expect(filterClients(mockClients, "  ")).toHaveLength(mockClients.length);
  });

  it("ignores case and diacritics", () => {
    expect(filterClients(mockClients, "dvorak").map((c) => c.name)).toEqual(["Lucie Dvořáková"]);
    expect(filterClients(mockClients, "ČERNÝ").map((c) => c.name)).toEqual(["Tomáš Černý"]);
  });

  it("matches by client ID", () => {
    expect(filterClients(mockClients, "cl-1026").map((c) => c.id)).toEqual(["CL-102611"]);
  });
});
