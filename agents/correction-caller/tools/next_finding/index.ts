import { s, w } from "@wonderful/types/schema";
import { getState, loadRow, parseFindings, setState } from "../../lib/request";

// The call is a quick overview; the email carries every finding.
const MAX_SPOKEN = 4;

// Capitalised words with Czech letters, e.g. "Výroba", that the model tends to
// write without accents.
function czechNames(text: string): string[] {
  const words = text.match(/[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+/g) ?? [];
  return [...new Set(words.filter((word) => /[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/.test(word)))].slice(0, 10);
}

export default w.tool({
  name: "next_finding",
  description: "Return the next finding to walk the verified client through, one at a time. Only works after verify_last_name succeeded.",
  params: s.object({}),
  handler: async (ctx) => {
    const state = getState(ctx);
    if (!state?.verified) return { error: "not_verified", instruction: "Verify the caller's surname first." };
    const row = await loadRow(ctx, state);
    if (!row) return { error: "no_request" };

    const findings = parseFindings(row.findings);
    const spoken = Math.min(findings.length, MAX_SPOKEN);
    if (state.findings_told >= spoken) {
      return {
        done: true,
        not_spoken: findings.length - spoken,
        reviewer_note: row.note || null,
        instruction: "All findings for the call are covered. Call send_findings_email.",
      };
    }

    const finding = findings[state.findings_told];
    state.findings_told += 1;
    setState(ctx, state);
    return {
      number: state.findings_told,
      of: spoken,
      finding,
      names: czechNames(`${finding.label} ${finding.found ?? ""}`),
      instruction:
        "Explain this finding in one short plain-English sentence. Copy any name from `names` exactly, letter for letter with its accents. If the client has to tell you or decide something about it, end with a short question and wait. Otherwise call next_finding right away, without waiting for a reply.",
    };
  },
});
