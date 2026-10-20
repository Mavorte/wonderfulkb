# Intake Chat

Conversational agent that collects a client's loan documents in a chat. It is embedded in the `client-intake-chat` app, a parallel to the Client Intake upload page, and uses the same `?h=<hash>` links.

## Flow

1. The opening line (`config.json`, chat channel) asks the client to upload their loan agreement. The client drags PDFs into the chat; attachments are enabled in `behavior.attachments`.
2. `check_loan_agreement` reads the newest upload with structured OCR (`ctx.ocr.extractTextFromAttachment`). It checks loosely that the file looks like a loan agreement and reads the documents it requires before disbursement. If the agreement lists none, `DEFAULT_REQUIRED_DOCUMENTS` in `lib/intake.ts` is used.
3. `check_documents` reads each later upload and checks loosely which required document it is. It returns what is still outstanding.
4. Once everything has arrived, `submit_documents` sends the loan agreement and the accepted documents to AWS ingest, the same way the Client Intake app's `intake-submit` does: one multipart POST to `{kb_aws_ingest_url}/cases/{case_id}/documents` with secret `kb-aws-ingest-api-key`. The agent then thanks the client.

The tools keep the progress in KV (`intake`): the accepted agreement, the required documents with the upload accepted for each, and every checked file. Only PDFs are accepted, as in Client Intake.

## Case

The chat page starts the session with metadata `intake_hash` = the link's `h` value. `submit_documents` resolves it to the case with the Client Intake app's `client-intake/intake-get` Function. A chat opened without that metadata, such as a test chat in Agent Studio, can check documents but cannot submit them.

## Code

| Path | Contents |
| --- | --- |
| `skills/document-intake/` | The single skill: its prompt and tool attachments. |
| `tools/*/index.ts` | The three tools. |
| `lib/intake.ts` | KV state, required documents and file helpers. |
| `lib/ingest.ts` | Case lookup and the ingest upload. |
| `lib/intake.test.ts` | Unit tests (`pnpm test`). |
