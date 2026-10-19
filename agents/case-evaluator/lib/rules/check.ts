// Shared shape of the per-rule validators: either a result to save or the
// problems that make the agent's input inconsistent.

import type { RuleResult } from "../run";

export type CheckOutcome = { result: RuleResult; problems?: undefined } | { problems: string[]; result?: undefined };

export function rejected(problems: string[]): CheckOutcome {
  return { problems };
}

export function requireReasoning(reasoning: string, problems: string[]): void {
  if (!reasoning.trim()) problems.push("reasoning is required: explain why you chose this status.");
}
