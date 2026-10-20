import { s, w } from "@wonderful/types/schema";
import { MAX_ATTEMPTS, findPending, setState, updateRow } from "../../lib/request";

const UNKNOWN_CALL = "Hello, I'm an AI assistant calling from Komerční banka. Sorry, I don't have the details for this call, we'll be in touch again.";

export default w.tool({
  name: "open_correction_call",
  description: "Runs when the call starts: loads the correction request for the dialed number and greets the client.",
  trigger: "OnStart",
  params: s.object({}),
  handler: async (ctx) => {
    const comm = ctx.metadata?.communication;
    const phoneNumber = comm?.direction === "outbound" ? comm?.toNumber : comm?.fromNumber;
    const request = phoneNumber ? await findPending(ctx, phoneNumber) : null;
    if (!request) {
      ctx.agent.announce(UNKNOWN_CALL);
      return { found: false, instruction: "There is no correction request for this call. Apologise briefly and call end_call." };
    }

    const state = { row_id: request.id, request_id: request.data.request_id, verified: false, attempts: 0, email_sent: false, findings_told: 0 };
    setState(ctx, state);
    await updateRow(ctx, state, { status: "in_call", communication_id: comm?.id ?? "" });

    const company = request.data.company_name;
    // Bias speech recognition toward the surname and company it is about to hear.
    try {
      ctx.transcriber.updateSessionConfig({ terms: [request.data.contact_last_name, company].filter(Boolean) });
    } catch (error) {
      console.log(`transcriber hints not applied: ${error instanceof Error ? error.message : String(error)}`);
    }
    ctx.agent.announce(
      `Hello, I'm an AI assistant from the loan review team at Komerční banka, calling about the loan application${company ? ` for ${company}` : ""}. ` +
        "First I need to verify who I'm speaking with. What is your last name?",
    );
    return {
      found: true,
      company_name: company,
      max_attempts: MAX_ATTEMPTS,
      instruction: "The greeting asking for the surname has been played. Wait for the surname, then call verify_last_name.",
    };
  },
});
