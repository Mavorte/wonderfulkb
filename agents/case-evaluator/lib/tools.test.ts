// Each *_contents and *_consistent tool writes its params out in full; these
// tests keep the enums there in step with the spec the validator checks against.

import { describe, expect, it } from "vitest";
import type { ConsistencySpec } from "./rules/consistency";
import * as consistencySpecs from "./rules/consistencySpecs";
import type { ContentsSpec } from "./rules/contents";
import * as contentSpecs from "./rules/contentSpecs";

const specs = <T>(module: Record<string, unknown>) =>
  Object.values(module).filter((v): v is T => typeof v === "object" && v !== null && "rule_id" in v);

const loadParams = async (rule_id: string) => (await import(`../tools/evaluate_${rule_id}/index.ts`)).default.params.toJsonSchema();

describe("contents tools", () => {
  it.each(specs<ContentsSpec>(contentSpecs).map((spec) => [spec.rule_id, spec] as const))("%s lists the spec's fields", async (rule_id, spec) => {
    const params = await loadParams(rule_id);
    expect(params.properties.fields.items.properties.field.enum).toEqual(spec.fields.map((f) => f.key));
  });
});

describe("consistency tools", () => {
  it.each(specs<ConsistencySpec>(consistencySpecs).map((spec) => [spec.rule_id, spec] as const))("%s lists the spec's attributes", async (rule_id, spec) => {
    const params = await loadParams(rule_id);
    expect(params.properties.attributes.items.properties.attribute.enum).toEqual(spec.attributes.map((a) => a.key));
    const textKeys = spec.attributes.filter((a) => a.kind === "text").map((a) => a.key);
    expect(params.properties.equivalent?.items.enum).toEqual(textKeys.length ? textKeys : undefined);
    expect(params.properties.status.enum.includes("not_applicable")).toBe(!!spec.optional);
  });
});
