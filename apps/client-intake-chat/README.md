# Client Intake Chat

Client-facing chat page, a parallel to the Client Intake upload page. The client opens a share link with the same `?h=<hash>` as Client Intake and talks to the **Intake Chat** agent (`repos/intake-chat/`). The agent asks for the loan agreement, reads the documents it requires, checks each PDF the client drags into the chat, and sends them to AWS ingest when everything is in.

## Flow

1. Link: `https://kb-hackathon.app.sb.wonderful.ai/s/<share-code>?h=<hash>`, with the hashes from Client Intake's `client_intake.intake_links` table.
2. `functions/chat-get` resolves the hash through Client Intake's `client-intake/intake-get` Function and returns the case and client details plus the Embedded Chat settings.
3. The page embeds the agent with `@wonderful/chat` (`renderConversation`). Every new chat session carries the metadata `intake_hash`, which the agent's `submit_documents` tool resolves to the case. Each link keeps its own conversation in the browser and resumes it when reopened.
4. The agent's tools do the OCR checks and the upload to `{kb_aws_ingest_url}/cases/{case_id}/documents`; see `repos/intake-chat/README.md`.

## Configuration

| Name | Kind | Value |
| --- | --- | --- |
| `intake_chat_sdk_key` | global variable | Client SDK key of the Intake Chat agent (Agent Studio → Channels → Embedded Chat). Publishable. |
| `intake_chat_agent_id` | global variable | `a47e88bb-2628-4c88-9741-f144a1ffce5f` (Intake Chat) |
| `intake_chat_api_url` | global variable | `https://kb-hackathon.api.sb.wonderful.ai` |

While any of the three is empty, the page shows the case and says the chat is not available. Embedded Chat must list `https://kb-hackathon.app.sb.wonderful.ai` under **Settings → Domains**.

The share link needs anonymous access enabled for the app. The anonymous audience must be allowed to call `chat-get`, and `chat-get` must be allowed to call `client-intake/intake-get`.
