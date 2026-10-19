import { s, w } from "@wonderful/types/schema";
import { NO_RUN } from "../../lib/record";
import { RULE_IDS, getVerdict } from "../../lib/rules";
import { finishRun, getRun, getStatuses } from "../../lib/run";

export default w.tool({
  name: "finish_evaluation",
  description:
    "Finish the evaluation once every rule is recorded. Rejected, with the rules still to record, if any is missing. Returns the verdict.",
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
    await finishRun(ctx, run, "completed", summary, verdict);
    return { accepted: true, evaluation_id: run.evaluation_id, verdict, statuses };
  },
});
