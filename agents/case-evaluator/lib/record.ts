// Common flow of the evaluate_* tools: check the agent's input against the run,
// then save the rule's result row.

import { type Region, anchorSources } from "./regions";
import { type Run, type RuleResult, type RunContext, getDocumentRegions, getRun, saveResult } from "./run";
import type { CheckOutcome } from "./rules/check";

export const NO_RUN = { accepted: false, problems: ["No evaluation is running. Call start_evaluation first."] };

// onSaved runs after the result row is saved, e.g. to keep run state that later rules check against.
export async function recordRule(ctx: RunContext, check: (run: Run) => CheckOutcome, onSaved?: (run: Run, result: RuleResult) => void) {
  const run = getRun(ctx);
  if (!run) return NO_RUN;
  const outcome = check(run);
  if (outcome.problems) return { accepted: false, problems: outcome.problems };
  const result = { ...outcome.result, sources: anchor(ctx, run, outcome.result) };
  await saveResult(ctx, run, result);
  onSaved?.(run, result);
  const { rule_id, status, expected, found } = outcome.result;
  return { accepted: true, rule_id, status, expected, found };
}

// Places the result's sources on the regions of their documents. Anchoring only
// adds detail, so a failure leaves the sources at page level (saveResult drops
// the lookup hints).
function anchor(ctx: RunContext, run: Run, result: RuleResult) {
  const cache = new Map<string, Region[] | null>();
  const regionsOf = (documentId: string) => {
    if (!cache.has(documentId)) cache.set(documentId, getDocumentRegions(ctx, run, documentId));
    return cache.get(documentId)!;
  };
  try {
    return anchorSources(result.sources, regionsOf);
  } catch (error) {
    console.log(`anchoring ${result.rule_id} failed: ${error}`);
    return result.sources;
  }
}
