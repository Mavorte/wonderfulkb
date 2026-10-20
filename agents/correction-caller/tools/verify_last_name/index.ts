import { s, w } from "@wonderful/types/schema";
import { MAX_ATTEMPTS, getState, lastCustomerUtterance, lastNameMatches, loadRow, parseFindings, setState, spokenCompanyName, updateRow } from "../../lib/request";

const RETRY = "Sorry, I couldn't verify that. Could you say your last name once more, or spell it for me?";
const LOCKED = "I'm sorry, I can't verify you right now. The bank will contact you another way. Goodbye.";

export default w.tool({
  name: "verify_last_name",
  description:
    "Check the surname the caller said against the contact person on file. On a match, returns the document problems to explain. Never reveals the name on file.",
  params: s.object({
    last_name: s
      .string()
      .describe("The caller's answer to the surname question exactly as transcribed, even if it does not look like a name, e.g. \"it's Novák\". Never guess or fill in a name."),
  }),
  handler: async (ctx, { last_name }) => {
    const state = getState(ctx);
    if (!state) return { verified: false, error: "no_request", instruction: "There is no correction request for this call. Call end_call." };
    const row = await loadRow(ctx, state);
    if (!row) return { verified: false, error: "no_request", instruction: "The request is gone. Apologise and call end_call." };

    if (!state.verified) {
      if (state.attempts >= MAX_ATTEMPTS) {
        return { verified: false, attempts_left: 0, say: LOCKED, instruction: "Say the `say` text word for word, then call end_call." };
      }
      state.attempts += 1;
      // The model may respell what it heard, so also check the raw transcript.
      const heard = [last_name, lastCustomerUtterance(ctx)];
      state.verified = heard.some((answer) => lastNameMatches(answer, row.contact_last_name));
      setState(ctx, state);
      if (!state.verified) {
        const attemptsLeft = MAX_ATTEMPTS - state.attempts;
        if (attemptsLeft === 0) await updateRow(ctx, state, { status: "verification_failed" });
        return {
          verified: false,
          attempts_left: attemptsLeft,
          say: attemptsLeft > 0 ? RETRY : LOCKED,
          instruction:
            attemptsLeft > 0
              ? "Say the `say` text word for word and nothing else. Do not hint at the name on file."
              : "Say the `say` text word for word, then call end_call. Share no case details.",
        };
      }
      await updateRow(ctx, state, { status: "verified" });
    }

    return {
      verified: true,
      say: "Thank you, that matches our records.",
      company_name: spokenCompanyName(row.company_name),
      findings_total: parseFindings(row.findings).length,
      instruction: "Say the `say` text, then call next_finding.",
    };
  },
});
