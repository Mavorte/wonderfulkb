import { describe, expect, it } from "vitest";
import { lastNameMatches, normalizeName, parseFindings, spokenCompanyName } from "./request";

describe("lastNameMatches", () => {
  it("ignores diacritics and case", () => {
    expect(lastNameMatches("kremenik", "Křemeník")).toBe(true);
    expect(lastNameMatches("KŘEMENÍK", "Křemeník")).toBe(true);
  });

  it("accepts the full name or a short sentence", () => {
    expect(lastNameMatches("Dalibor Křemeník", "Křemeník")).toBe(true);
    expect(lastNameMatches("je to Křemeník", "Křemeník")).toBe(true);
  });

  it("tolerates a misheard letter or two", () => {
    expect(lastNameMatches("Křemenik", "Křemeník")).toBe(true);
    expect(lastNameMatches("Kremeňík", "Křemeník")).toBe(true);
    expect(lastNameMatches("Křemínek", "Křemeník")).toBe(true);
    expect(lastNameMatches("Nová", "Novák")).toBe(true);
    expect(lastNameMatches("Nov", "Novák")).toBe(false);
    expect(lastNameMatches("Kremeshnik", "Křemeník")).toBe(true);
    expect(lastNameMatches("Přemešník", "Křemeník")).toBe(true);
  });

  it("rejects a different surname", () => {
    expect(lastNameMatches("Novák", "Křemeník")).toBe(false);
    expect(lastNameMatches("To není", "Křemeník")).toBe(false);
  });

  it("rejects a list of surnames in one answer", () => {
    expect(lastNameMatches("Novák Svoboda Dvořák Křemeník", "Křemeník")).toBe(false);
  });

  it("never matches an empty name on file", () => {
    expect(lastNameMatches("", "")).toBe(false);
    expect(lastNameMatches("Novák", "")).toBe(false);
  });
});

describe("normalizeName", () => {
  it("keeps only bare letters", () => {
    expect(normalizeName("Nová-Kováčová ")).toBe("novakovacova");
  });
});

describe("parseFindings", () => {
  it("reads the findings list", () => {
    expect(parseFindings('[{"label":"Invoice","found":"Wrong buyer"}]')).toEqual([{ label: "Invoice", found: "Wrong buyer" }]);
  });

  it("returns nothing for invalid JSON", () => {
    expect(parseFindings("not json")).toEqual([]);
    expect(parseFindings('{"label":"x"}')).toEqual([]);
  });
});

describe("spokenCompanyName", () => {
  it("drops the legal form and keeps the accents", () => {
    expect(spokenCompanyName("Plastovra Výroba s.r.o.")).toBe("Plastovra Výroba");
    expect(spokenCompanyName("Kompavex Servis, spol. s r.o.")).toBe("Kompavex Servis");
    expect(spokenCompanyName("Stavby Fišer a.s.")).toBe("Stavby Fišer");
    expect(spokenCompanyName("Agroluh Vřesava")).toBe("Agroluh Vřesava");
  });
});
