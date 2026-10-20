import { s, w } from "@wonderful/types/schema";
import { MAX_ATTEMPTS, getState, lastNameMatches, loadRow, parseFindings, setState, updateRow } from "../../lib/request";

const RETRY = "Promiňte, to se mi nepodařilo ověřit. Řekněte mi prosím své příjmení ještě jednou, klidně ho i hláskujte.";
const LOCKED = "Bohužel vás teď nemohu ověřit. Banka se vám ozve jinou cestou. Na shledanou.";

export default w.tool({
  name: "verify_last_name",
  description:
    "Check the surname the caller said against the contact person on file. On a match, returns the document problems to explain. Never reveals the name on file.",
  params: s.object({
    last_name: s
      .string()
      .describe("The caller's answer to the surname question exactly as transcribed, even if it does not look like a name, e.g. 'je to Novák'. Never guess or fill in a name."),
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
      state.verified = lastNameMatches(last_name, row.contact_last_name);
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
      company_name: row.company_name,
      findings: parseFindings(row.findings),
      reviewer_note: row.note || null,
      instruction:
        "In one or two short Czech sentences, summarise the main problem. Do not go through every finding. Then call send_findings_email.",
    };
  },
});
