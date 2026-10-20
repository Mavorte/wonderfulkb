import { describe, expect, it } from "vitest";
import { lastNameMatches, normalizeName, parseFindings } from "./request";

describe("lastNameMatches", () => {
  it("ignores diacritics and case", () => {
    expect(lastNameMatches("kremenik", "Křemeník")).toBe(true);
    expect(lastNameMatches("KŘEMENÍK", "Křemeník")).toBe(true);
  });

  it("accepts the full name", () => {
    expect(lastNameMatches("Dalibor Křemeník", "Křemeník")).toBe(true);
  });

  it("rejects a different surname", () => {
    expect(lastNameMatches("Novák", "Křemeník")).toBe(false);
    expect(lastNameMatches("Křemen", "Křemeník")).toBe(false);
  });

  it("rejects a list of surnames in one answer", () => {
    expect(lastNameMatches("Novák Svoboda Křemeník", "Křemeník")).toBe(false);
    expect(lastNameMatches("Křemeník Novák", "Křemeník")).toBe(false);
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
