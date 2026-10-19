import { test } from "node:test";
import assert from "node:assert/strict";
import { createClientsQuery, toClientOption } from "./query.ts";

test("createClientsQuery lists all clients for an empty search", () => {
  assert.equal(createClientsQuery("  "), "limit=20");
});

test("createClientsQuery matches a number by IČO", () => {
  assert.equal(createClientsQuery(" 12345678 "), "limit=20&ico=12345678");
});

test("createClientsQuery waits for all eight IČO digits", () => {
  assert.equal(createClientsQuery("1234"), null);
});

test("createClientsQuery searches anything else by name", () => {
  assert.equal(createClientsQuery("fiser"), "limit=20&name=fiser&status=active");
  assert.equal(createClientsQuery("Solom Rec 2"), "limit=20&name=Solom+Rec+2&status=active");
});

test("createClientsQuery skips a one-character name", () => {
  assert.equal(createClientsQuery("S"), null);
});

test("toClientOption keeps only what the autocomplete shows", () => {
  assert.deepEqual(
    toClientOption({ client_id: "c1", ico: "04606812", name: "Solom Rec s.r.o.", status: "active", legal_form: "s.r.o." }),
    { id: "c1", ico: "04606812", name: "Solom Rec s.r.o.", status: "active" },
  );
});
