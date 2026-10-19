// Common flow of the evaluate_* tools: check the agent's input against the run,
// then save the rule's result row.

import { type Run, type RuleResult, type RunContext, getRun, saveResult } from "./run";
import type { CheckOutcome } from "./rules/check";

export const NO_RUN = { accepted: false, problems: ["No evaluation is running. Call start_evaluation first."] };

// onSaved runs after the result row is saved, e.g. to keep run state that later rules check against.
export async function recordRule(ctx: RunContext, check: (run: Run) => CheckOutcome, onSaved?: (run: Run, result: RuleResult) => void) {
  const run = getRun(ctx);
  if (!run) return NO_RUN;
  const outcome = check(run);
  if (outcome.problems) return { accepted: false, problems: outcome.problems };
  await saveResult(ctx, run, outcome.result);
  onSaved?.(run, outcome.result);
  const { rule_id, status, expected, found } = outcome.result;
  return { accepted: true, rule_id, status, expected, found };
}
