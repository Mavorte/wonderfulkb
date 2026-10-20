import { s, w } from "@wonderful/types/schema";
import { getState, loadRow, setState, updateRow } from "../../lib/request";

export default w.tool({
  name: "send_upload_link",
  description: "Send the verified client an SMS with the link where they upload the corrected documents. Only works after verify_last_name succeeded.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (!state?.verified) return { sent: false, error: "not_verified", instruction: "Verify the caller's surname first." };
    if (state.sms_sent) return { sent: true, already_sent: true };
    const row = await loadRow(ctx, state);
    if (!row?.upload_link) {
      return { sent: false, error: "no_upload_link", instruction: "Say the bank will send the upload link separately." };
    }

    const message = `Komerční banka: nahrajte prosím opravené dokumenty k žádosti o úvěr${row.company_name ? ` (${row.company_name})` : ""} zde: ${row.upload_link}`;
    try {
      await ctx.telephony.sendSms(row.phone_number, message);
    } catch (error) {
      await updateRow(ctx, state, { status: "sms_failed" });
      return {
        sent: false,
        error: error instanceof Error ? error.message : String(error),
        instruction: "Say the SMS could not be sent right now and the bank will send the link again shortly.",
      };
    }
    state.sms_sent = true;
    setState(ctx, state);
    await updateRow(ctx, state, { status: "sms_sent", sms_sent_at: new Date().toISOString() });
    return { sent: true, instruction: "Tell the client the SMS with the upload link has just been sent to this phone number." };
  },
});
