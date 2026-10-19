# Host IAM change and authorized continuation — 2026-10-19 17:49

User message1561768386772471900 explicitly authorizes fixing test-environment access and another bounded deployment/integration attempt; no broad new testing framework requested.

Host verified STS account609394381050, regioneu-central-1, Lambda wonderfulkb-case-client's actual execution role wonderfulkb-lambda-role. Inspected existing inline/attached policies and permission boundary before mutation. Original inline policies saved privately with mode600, directory700, under /Users/michal/.openclaw/tmp/opencode/case-client-iam-20261019/. No credentials or table data read/changed by this operation.

Added separate inline policy `case-client-active-condition-check`:
- Effect Allow
- Action dynamodb:ConditionCheckItem
- Resource arn:aws:dynamodb:eu-central-1:609394381050:table/wonderfulkb-uw-clients

Readback exactly matches. SimulatePrincipalPolicy with aws:RequestedRegion=eu-central-1 yields allowed, no missing context. This proves policy configuration/evaluation, not a successful real POST. No other inline/managed/trust policy changed, no table/schema/data modification. Full cross-region role-user discovery remains inaccessible; the user explicitly approves this exact additive policy change despite the earlier procedural discovery hold. No SCP or actual access control bypassed.

Recovery for IAM change, if requested/needed: remove only this newly added policy, leaving original policies intact. Original Lambda runtime observed before policy change was nodejs22.x; no deploy performed by host in this step.

Existing task beca6825 canonical brief rewritten under active ownership, then public forced reset→backlog and start: fresh planning dark-crag-1877/PID79669; old runtime73039 stopped, stale plan cleared. New continuation max3forward+1rollback/30min, no more than6newPOSTs, reuse4syntheticclients; original5attempt manifest/POST ambiguity/rollback remain historical. Separate run accounting required, not a silent reset of old counters. Canonical reset removed the operational task checkpoint by design; original durable live manifest/review/proof files retained. No successor released, no old acceptance marked green.
