// Resolves an intake link hash for the chat page. The links are the Client
// Intake app's (`client_intake.intake_links`), so the lookup goes through its
// intake-get Function, which also returns the case and client details.
//
// Configuration (tenant-level globals) for the embedded Intake Chat agent:
// - `intake_chat_sdk_key`: the agent's Client SDK key from Agent Studio →
//   Channels → Embedded Chat. It is publishable, so it is safe to return.
// - `intake_chat_agent_id`: the Intake Chat agent's ID.
// - `intake_chat_api_url`: the Wonderful API base the widget talks to,
//   e.g. https://kb-hackathon.api.sb.wonderful.ai
// While any of them is empty, `chat` is null and the page says chat is unavailable.

import type { FunctionContext } from "@wonderful/types";
import type { ChatConfig, ChatPageData } from "../../app/src/types";

type ChatGetError = { error: "missing_hash" | "invalid_link" | "case_not_found" | "upstream" };

// Missing globals throw at runtime instead of returning null.
function getGlobal(context: FunctionContext, name: string): string {
  try {
    return String(context.globals.get(name) ?? "").trim();
  } catch {
    return "";
  }
}

function getChatConfig(context: FunctionContext): ChatConfig | null {
  const config = {
    sdk_key: getGlobal(context, "intake_chat_sdk_key"),
    agent_id: getGlobal(context, "intake_chat_agent_id"),
    api_url: getGlobal(context, "intake_chat_api_url").replace(/\/+$/, ""),
  };
  return config.sdk_key && config.agent_id && config.api_url ? config : null;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function userFunction(context: FunctionContext): Promise<ChatPageData | ChatGetError> {
  const hash = String(context.data?.hash || "").trim();
  if (!hash) {
    context.response.setStatus(400);
    return { error: "missing_hash" };
  }

  let result: Record<string, any>;
  try {
    result = context.functions.run({ slug: "client-intake/intake-get", params: { hash } }).result;
  } catch (error) {
    console.log(`intake-get failed: ${getErrorMessage(error)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }

  if (result?.error === "missing_hash" || result?.error === "invalid_link" || result?.error === "case_not_found") {
    context.response.setStatus(result.error === "missing_hash" ? 400 : 404);
    return { error: result.error };
  }
  if (result?.error || !result?.case_id) {
    console.log(`intake-get returned ${JSON.stringify(result).slice(0, 200)}`);
    context.response.setStatus(502);
    return { error: "upstream" };
  }

  return { ...(result as ChatPageData), chat: getChatConfig(context) };
}
