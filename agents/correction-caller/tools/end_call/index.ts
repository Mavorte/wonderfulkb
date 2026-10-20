import { s, w } from "@wonderful/types/schema";
import { REQUESTS_TABLE, getState, updateRow } from "../../lib/request";

// Statuses that already say how the call ended.
const FINAL = new Set(["email_sent", "verification_failed"]);

export default w.tool({
  name: "end_call",
  description: "Hang up after the goodbye has been said.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (state && !state.email_sent) {
      const status = state.verified ? "ended" : "ended_unverified";
      try {
        const row = await ctx.tables.getRow(REQUESTS_TABLE, state.row_id);
        if (!FINAL.has(String(row?.data?.status))) await updateRow(ctx, state, { status });
      } catch (error) {
        console.log(`call end status not saved: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    ctx.telephony.end(true);
    return { ended: true };
  },
});
