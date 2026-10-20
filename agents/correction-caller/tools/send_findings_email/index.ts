import { s, w } from "@wonderful/types/schema";
import { getState, loadRow, setState, updateRow } from "../../lib/request";

// Email delivery is mocked: the full findings and the upload link are treated as
// sent to the client's address on file, and the request is marked accordingly.
export default w.tool({
  name: "send_findings_email",
  description:
    "Email the verified client the full list of findings and the link where they upload the corrected documents. Only works after verify_last_name succeeded.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (!state?.verified) return { sent: false, error: "not_verified", instruction: "Verify the caller's surname first." };
    if (state.email_sent) return { sent: true, already_sent: true };
    const row = await loadRow(ctx, state);
    if (!row) return { sent: false, error: "no_request" };

    state.email_sent = true;
    setState(ctx, state);
    await updateRow(ctx, state, { status: "email_sent" });
    return { sent: true, instruction: "Tell the client the email with all findings and the upload link has been sent to their address on file." };
  },
});
