import { createChat, createWonderful, renderConversation, type Wonderful } from "@wonderful/chat";
import { useEffect, useRef } from "react";
import type { ChatConfig } from "../types";

// Every new session carries the intake link's hash as metadata. The agent's
// submit_documents tool resolves the case from it.
function withIntakeHash(client: Wonderful, hash: string): Wonderful {
  return new Proxy(client, {
    get(target, prop) {
      if (prop === "createSession") {
        return (options?: Parameters<Wonderful["createSession"]>[0]) =>
          typeof options === "string"
            ? target.createSession(options)
            : target.createSession({ ...options, metadata: { ...options?.metadata, intake_hash: hash } });
      }
      const value = Reflect.get(target, prop, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

// The Intake Chat agent's conversation, filling the panel. Files dragged into
// it are uploaded to the conversation for the agent to check.
export default function ChatPanel({ config, hash }: { config: ChatConfig; hash: string }) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    // A storage key per link keeps each case's conversation separate in the same browser,
    // and resumes it when the link is opened again.
    const client = createWonderful({
      key: config.sdk_key,
      agentId: config.agent_id,
      baseUrl: config.api_url,
      storageKey: `kb-intake-chat:${hash}`,
    });
    // The platform's single-request upload route sits behind a Cloudflare rule that
    // blocks real loan PDFs (403, which the browser reports as a network error). The
    // SDK's other path uploads the bytes straight to S3 with a presigned URL; this
    // flag is what makes it take that path for every file.
    (client as Wonderful & { missingUploadEndpoint?: boolean }).missingUploadEndpoint = true;
    const chat = createChat({
      client: withIntakeHash(client, hash),
      agentId: config.agent_id,
      baseUrl: config.api_url,
      header: { title: "Asistent KB" },
      locale: "cs",
      // The agent reads every uploaded PDF before it answers, which takes well over
      // the SDK's default 30 seconds for a batch of files. Without this the chat
      // shows "Agent neodpovídá" while the answer is still on its way.
      replyTimeoutMs: 180_000,
      theme: "light",
      appearance: {
        primary: "#e00000",
        primaryForeground: "#f9f9f9",
        radius: "12px",
        surfaceOpacity: 1,
        fontFamily: "inherit",
      },
    });
    const view = renderConversation(chat, host);
    return () => view.destroy();
  }, [config, hash]);

  return <div ref={hostRef} className="chat-host" />;
}
