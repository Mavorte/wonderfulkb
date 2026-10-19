import { s, w } from "@wonderful/types/schema";
import { finishRun, getRun } from "../../lib/run";

export default w.tool({
  name: "fail_evaluation",
  description:
    "Mark the running evaluation as failed when it can't be completed, e.g. a tool keeps failing after start_evaluation. Not for case findings: those are recorded with the evaluate_* tools.",
  params: s.object({
    reason: s.string().describe("What went wrong, e.g. which tool failed and its error."),
  }),
  handler: async (ctx, { reason }) => {
    const run = getRun(ctx);
    if (!run) return { accepted: true, note: "No evaluation was started, so there is nothing to mark." };
    await finishRun(ctx, run, "failed", reason);
    return { accepted: true, evaluation_id: run.evaluation_id, status: "failed" };
  },
});
