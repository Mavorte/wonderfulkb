import { s, w } from "@wonderful/types/schema";

export default w.tool({
  name: "end_call",
  description: "Hang up after the goodbye has been said.",
  params: s.object({}),
  handler: async (ctx) => {
    ctx.telephony.end(true);
    return { ended: true };
  },
});
