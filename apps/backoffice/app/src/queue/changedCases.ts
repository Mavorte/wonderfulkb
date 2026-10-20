import type { TriagedCase } from "./triage.ts";

/** Ids of the cases whose status differs from the last list; cases new to the list do not count. */
export default function changedCases(previous: TriagedCase[] | undefined, next: TriagedCase[]): Set<string> {
  const before = new Map(previous?.map((c) => [c.case_id, c.status]));
  return new Set(next.filter((c) => before.has(c.case_id) && before.get(c.case_id) !== c.status).map((c) => c.case_id));
}
