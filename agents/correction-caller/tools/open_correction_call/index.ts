import { s, w } from "@wonderful/types/schema";
import { MAX_ATTEMPTS, findPending, setState, updateRow } from "../../lib/request";

const UNKNOWN_CALL = "Dobrý den, tady Komerční banka. Omlouvám se, k tomuto hovoru teď nemám podklady, ozveme se vám znovu.";

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

    const state = { row_id: request.id, request_id: request.data.request_id, verified: false, attempts: 0, sms_sent: false };
    setState(ctx, state);
    await updateRow(ctx, state, { status: "in_call", communication_id: comm?.id ?? "" });

    const company = request.data.company_name;
    ctx.agent.announce(
      `Dobrý den, tady Komerční banka. Volám kvůli žádosti o úvěr${company ? ` společnosti ${company}` : ""}. ` +
        "Než budeme pokračovat, potřebuji ověřit, že mluvím se správnou osobou. Řekněte mi prosím své příjmení.",
    );
    return {
      found: true,
      company_name: company,
      max_attempts: MAX_ATTEMPTS,
      instruction: "The greeting asking for the surname has been played. Wait for the surname, then call verify_last_name.",
    };
  },
});
