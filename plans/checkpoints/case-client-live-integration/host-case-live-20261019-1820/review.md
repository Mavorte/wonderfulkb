# Host manual deployment and live verification — 2026-10-19

User18:20 explicitly requested direct live verification and manual deployment if missing. Existing unused IAM1750 continuation used with separate host evidence and private snapshot; historical five-attempt rollback manifest unchanged. No project executable files changed, no new fixture clients, no IAM/API modifications.

## Observed and executed
- STS account609394381050, profileai-hackathon, regioneu-central-1 verified. Original Lambda wonderfulkb-case-client was nodejs22.x/handler.handler,hashkgcHb9h9og06ykIX8OaV+JY3rzj35Ci44/xWNdyeFlA=. HTTP baseline missing/wrong key403,authenticatedGET/clients200.
- Existing deploy/preflight/snapshot/build/revision-checked update+verify functions reused. Private originalZIP/config backup verified before mutation; download URL/config/secrets not in repository. API4protectedAWS_PROXY routes and table/index bindings checked by preflight. Original snapshot recovery uses existing rollback owner with host evidence context, not historical task pointer.
-70component tests passed using dedicatedcase-clientvenv. Built current src with Linuxx86_64Python3.13binary dependencies. One forward deploy attempt, no rollback needed.
- Artifact+deployedCodeSha2566obGwm2G6bohQWeRvcDsVcH1sPJKqMYWk/euh3HQ2sA=verified before and after matrix, Runtimepython3.13,handlercase_client_handler.lambda_handler,rolewonderfulkb-lambda-role,DATA_BACKENDdynamodb,ALLOW_EPHEMERAL_MOCKfalse,originaltable/indexbindings.
- Existing boto3 SSO refresher initially reported expiredtoken while supportedAWSCLIprofile succeeded. Reused current profile credentials via AWSCLI export directly into process memory; no credentials printed/stored or profile edits. Initial failed connection made no mutation.

## Narrow live matrix PASS
5POSTs total(max6);no retries,serialrequestswith existing limiter,existing4syntheticclients reused,original ambiguousPOSTnot replayed.
-2POST201,same caller case_id ignored,distinctUUIDv4 generated; each immediatelyGET200with identicalresponse/metadata.
- Created IDs9fbe90e5-c36d-4986-8b52-d6b53ccf5a6f and80bfafac-7906-4a3a-81fa-a1c2fd51a9a1.
- Unknownclient404,inactive409,blocked409.
- Client-scoped cases list contains both createdIDs; prior cases preserved.
- Missing/wrong key403;all authenticatedcases responses carrieddynamodb marker in addition to actual matchingobjects/readbacks.
- No data deletion or client creation. Historical manifests unchanged. Sanitized hostmanifest records individual reservations/results and exact artifacthash.

This is actual deployed-state/manualHTTPevidence, NOT independent acceptance or registered fullTestGate success. Failedtask0228697f remains failed/inconclusive; no lifecycle overrides or budget resets performed.
