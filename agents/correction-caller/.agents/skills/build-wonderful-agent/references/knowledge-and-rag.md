# Knowledge and RAG Reference

Read this reference before creating, uploading, or attaching a knowledge base.

## Separate resource and repository lifecycles

A knowledge base is a workspace resource with uploaded documents. It is not stored in the agent repository. The repository stores only a pointer at `kbs/<slug>/kb.json`, and agent configuration or a skill attaches that pointer by slug.

Create and inspect the workspace resource with `wful`:

```bash
wful rags list
wful rags create --name "Billing docs" --slug billing-docs --file faq.pdf
wful rags file-list billing-docs
```

Then run `wful agents schema`, create or update the matching `kbs/billing-docs/kb.json` using the generated schema, and attach the slug in the component that needs it. A repository push validates that the slug exists in the selected workspace and does not collide with a tool name.

## Safe workflow

1. Reuse an existing knowledge base when its documents and retrieval scope fit.
2. Upload and wait for indexing before testing the agent.
3. Attach a knowledge base to the narrowest appropriate scope: a specific skill unless the intended behavior is agent-wide.
4. Run `wful validate`, push, and run `wful validate --remote` after changing the pointer or attachment.

Do not copy document contents into `kb.json`, invent a slug, or rename a workspace RAG without updating every repository pointer that uses it.
