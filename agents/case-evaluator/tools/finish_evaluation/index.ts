import { s, w } from "@wonderful/types/schema";
import { isError, runFunction } from "../../lib/functions";
import { NO_RUN } from "../../lib/record";
import { RULE_IDS, getVerdict } from "../../lib/rules";
import { finishRun, getRun, getStatuses } from "../../lib/run";

export default w.tool({
  name: "finish_evaluation",
  description:
    "Finish the evaluation once every rule is recorded. Rejected, with the rules still to record, if any is missing. Returns the verdict and moves the case to awaiting_decision for the KB worker.",
  params: s.object({
    summary: s.string().describe("Two to four sentences for the reviewer: the verdict and what must be fixed, if anything."),
  }),
  handler: async (ctx, { summary }) => {
    const run = getRun(ctx);
    if (!run) return NO_RUN;
    if (!summary.trim()) return { accepted: false, problems: ["summary is required."] };
    const statuses = await getStatuses(ctx, run);
    const missing = RULE_IDS.filter((id) => !statuses[id]);
    if (missing.length) return { accepted: false, problems: [`Record these rules first: ${missing.join(", ")}.`] };
    const verdict = getVerdict(Object.values(statuses) as string[]);
    // First, so a failure leaves the run open and this tool can be called again.
    const status = runFunction(ctx, "case-status-set", { case_id: run.case_id, status: "awaiting_decision" });
    if (isError(status)) {
      return { accepted: false, problems: [`The case status could not be set to awaiting_decision (${status.error}${status.message ? `: ${status.message}` : ""}). Call finish_evaluation again; if it keeps failing, call fail_evaluation.`] };
    }
    await finishRun(ctx, run, "completed", summary, verdict);
    return { accepted: true, evaluation_id: run.evaluation_id, verdict, statuses, case_status: "awaiting_decision" };
  },
});
