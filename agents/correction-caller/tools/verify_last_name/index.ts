import { s, w } from "@wonderful/types/schema";
import { MAX_ATTEMPTS, getState, lastNameMatches, loadRow, parseFindings, setState, updateRow } from "../../lib/request";

export default w.tool({
  name: "verify_last_name",
  description:
    "Check the surname the caller said against the contact person on file. On a match, returns the document problems to explain. Never reveals the name on file.",
  params: s.object({
    last_name: s.string().describe("The surname exactly as the caller said it, e.g. 'Novák'. Never guess or fill in a name the caller did not say."),
  }),
  handler: async (ctx, { last_name }) => {
    const state = getState(ctx);
    if (!state) return { verified: false, error: "no_request", instruction: "There is no correction request for this call. Call end_call." };
    const row = await loadRow(ctx, state);
    if (!row) return { verified: false, error: "no_request", instruction: "The request is gone. Apologise and call end_call." };

    if (!state.verified) {
      if (state.attempts >= MAX_ATTEMPTS) {
        return { verified: false, attempts_left: 0, instruction: "Verification is locked. Say you cannot continue and call end_call." };
      }
      state.attempts += 1;
      state.verified = lastNameMatches(last_name, row.contact_last_name);
      setState(ctx, state);
      if (!state.verified) {
        const attemptsLeft = MAX_ATTEMPTS - state.attempts;
        if (attemptsLeft === 0) await updateRow(ctx, state, { status: "verification_failed" });
        return {
          verified: false,
          attempts_left: attemptsLeft,
          instruction:
            attemptsLeft > 0
              ? "The surname does not match. Do not say why or hint at the right name. Ask the caller to repeat or spell their surname."
              : "Verification failed. Say politely that you cannot discuss the case and that the bank will contact them again, then call end_call. Share no case details.",
        };
      }
      await updateRow(ctx, state, { status: "verified" });
    }

    return {
      verified: true,
      company_name: row.company_name,
      findings: parseFindings(row.findings),
      reviewer_note: row.note || null,
      instruction:
        "In one or two short Czech sentences, summarise the main problem. Do not go through every finding. Then call send_findings_email.",
    };
  },
});
