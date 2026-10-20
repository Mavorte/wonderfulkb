#!/usr/bin/env bash
# Document trigger: DynamoDB Stream -> SQS -> worker Lambda. NIC SE NESPUSTI BEZ SOUHLASU UZIVATELE.
#
#   ./deploy.sh --plan      read only: checks, what would be created/changed, backfill estimate. Builds nothing.
#   ./deploy.sh stream      step 1: enable the stream on wonderfulkb-uw-documents (update of the stack
#                           wonderfulkb-documents-table with documents-table-with-stream.yaml; shows the change set first)
#   ./deploy.sh trigger     step 2: ECR repository + worker image + stack wonderfulkb-trigger (needs step 1)
#   ./deploy.sh rollback    removes stack wonderfulkb-trigger and wonderfulkb-trigger-ecr, then restores the original
#                           table template (the stream is switched off). Data in the tables is never touched.
# Every step that changes something asks you to type its name. Optional: AlarmTopicArn, SignatureKmsKeyArn,
# MaxConcurrency, BedrockRpm, WorkerMemory as environment variables of the same name (see template.yaml).
# The KMS key ARN of the signature crops is read from alias/wonderfulkb-signatures (read only).
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export AWS_PROFILE="${AWS_PROFILE:-hackathon}" AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 SAM_CLI_TELEMETRY=0
TABLES_STACK=wonderfulkb-documents-table
TRIGGER_STACK=wonderfulkb-trigger
ECR_STACK=wonderfulkb-trigger-ecr
DOCS_TABLE=wonderfulkb-uw-documents
ANALYSIS_TABLE=wonderfulkb-uw-document-analysis
RAW_BUCKET=wonderfulkb-raw-document-storage
ORIGINAL_TEMPLATE="$(cd "$SCRIPT_DIR/../../be-intake/documents-table" && pwd)/template.yaml"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
SAM=.venv-lint/bin/sam; [ -x "$SAM" ] || SAM=$(command -v sam || true)
LINT=.venv-lint/bin/cfn-lint; [ -x "$LINT" ] || LINT=$(command -v cfn-lint || true)

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
[ "$ACCOUNT" = "<ACCOUNT_ID>" ] || { echo "Wrong account $ACCOUNT (expected <ACCOUNT_ID>)." >&2; exit 1; }

confirm() { local answer; read -r -p "Type \"$1\" to continue: " answer; [ "$answer" = "$1" ] || { echo "Cancelled."; exit 1; }; }
stack_exists() { aws cloudformation describe-stacks --stack-name "$1" >/dev/null 2>&1; }
kms_arn() { aws kms describe-key --key-id alias/wonderfulkb-signatures --query KeyMetadata.Arn --output text 2>/dev/null | sed 's/^None$//'; }
stream_arn() { aws dynamodb describe-table --table-name "$DOCS_TABLE" --query 'Table.LatestStreamArn' --output text 2>/dev/null | sed 's/^None$//'; }

plan() {
  local ok=1
  chk() { if "${@:2}" >/dev/null 2>&1; then echo "  ok       $1"; else echo "  MISSING  $1"; ok=0; fi; }
  absent() { if "${@:2}" >/dev/null 2>&1; then echo "  EXISTS   $1 (the deploy would collide)"; ok=0; else echo "  free     $1"; fi; }
  echo "== Account $ACCOUNT, $AWS_REGION, profile $AWS_PROFILE =="
  echo "Dependencies:"
  chk "DynamoDB $DOCS_TABLE" aws dynamodb describe-table --table-name "$DOCS_TABLE"
  chk "DynamoDB $ANALYSIS_TABLE" aws dynamodb describe-table --table-name "$ANALYSIS_TABLE"
  chk "S3 bucket $RAW_BUCKET" aws s3api head-bucket --bucket "$RAW_BUCKET"
  chk "Stack $TABLES_STACK" aws cloudformation describe-stacks --stack-name "$TABLES_STACK"
  chk "KMS alias/wonderfulkb-signatures (crop encryption, redaction is on by default)" aws kms describe-key --key-id alias/wonderfulkb-signatures
  if aws dynamodb describe-table --table-name wonderfulkb-uw-content-hashes >/dev/null 2>&1; then echo "  ok       DynamoDB wonderfulkb-uw-content-hashes (dedup index)"; else echo "  note     DynamoDB wonderfulkb-uw-content-hashes missing: the dedup step of the pipeline degrades, the worker is granted access to it anyway"; fi
  chk "Bedrock/S3 Vectors index wonderfulkb-text" aws s3vectors get-index --vector-bucket-name wonderfulkb-vectors --index-name wonderfulkb-text
  echo "Names the stacks would take:"
  for n in "$TRIGGER_STACK" "$ECR_STACK"; do absent "stack $n" aws cloudformation describe-stacks --stack-name "$n"; done
  for q in wonderfulkb-trigger-documents wonderfulkb-trigger-documents-dlq; do absent "SQS queue $q" aws sqs get-queue-url --queue-name "$q"; done
  for f in enqueue worker dlq; do
    absent "Lambda wonderfulkb-trigger-$f" aws lambda get-function --function-name "wonderfulkb-trigger-$f"
    absent "IAM role wonderfulkb-trigger-$f" aws iam get-role --role-name "wonderfulkb-trigger-$f"
  done
  absent "ECR repository wonderfulkb-trigger-worker" aws ecr describe-repositories --repository-names wonderfulkb-trigger-worker
  echo
  echo "Account limits (Lambda):"
  aws lambda get-account-settings --query 'AccountLimit.{ConcurrentExecutions:ConcurrentExecutions,Unreserved:UnreservedConcurrentExecutions}' --output text |
    awk '{ printf "  concurrent executions %s, unreserved %s  -> a reservation of 2 would leave %d (AWS needs 10): reserved concurrency is NOT used, the SQS mapping limits workers to MaximumConcurrency instead\n", $1, $2, $2-2 }'
  echo
  echo "Stream on $DOCS_TABLE today:"
  aws dynamodb describe-table --table-name "$DOCS_TABLE" --query 'Table.{StreamSpecification:StreamSpecification,LatestStreamArn:LatestStreamArn,Items:ItemCount}' --output json
  echo
  echo "Step 1 (stream): change of stack $TABLES_STACK = the independent copy minus the deployed template:"
  local deployed; deployed=$(mktemp)
  aws cloudformation get-template --stack-name "$TABLES_STACK" --template-stage Original --query TemplateBody --output text > "$deployed"
  if "$PY" - "$deployed" "$ORIGINAL_TEMPLATE" <<'PYEOF'
import sys, yaml
a, b = (yaml.safe_load(open(p)) for p in sys.argv[1:3])
sys.exit(0 if a["Resources"] == b["Resources"] else 1)
PYEOF
  then echo "  deployed template matches $ORIGINAL_TEMPLATE (resources identical), so the diff below is the whole change"
  else echo "  WARNING: the deployed template differs from $ORIGINAL_TEMPLATE; compare by hand before step 1"; fi
  diff "$deployed" documents-table-with-stream.yaml | sed 's/^/  /' || true
  rm -f "$deployed"
  echo "  (StreamSpecification: update without interruption, no replacement, no data change; Output StreamArn added)"
  echo
  cat <<TEXT
Step 2 (trigger): creates (all tagged project=wonderfulkb, all names prefixed wonderfulkb-trigger):
  - stack $ECR_STACK: ECR repository wonderfulkb-trigger-worker (scan on push, keeps the last 5 images)
  - stack $TRIGGER_STACK:
      SQS wonderfulkb-trigger-documents (visibility 1200 s, SSE, DLQ after 3 receives) and ...-dlq (14 days)
      Lambda wonderfulkb-trigger-enqueue  (zip, python3.14 arm64, 256 MB, 60 s)   stream INSERT -> queued row + message
      Lambda wonderfulkb-trigger-worker   (image, x86_64, ${WorkerMemory:-3008} MB, 900 s, 2 GB /tmp)  SQS -> pipeline.run_document
          event source mapping: batch 1, MaximumConcurrency ${MaxConcurrency:-2}; BEDROCK rpm per worker ${BedrockRpm:-12}
      Lambda wonderfulkb-trigger-dlq      (zip, 256 MB)                            DLQ -> row 'failed' + reason + metric
      PIPELINE_REDACT=1 (signatures masked before anything reads the document), KMS: GenerateDataKey + DescribeKey only, no Decrypt
      3 IAM roles (least privilege, see template.yaml), 3 log groups (14 days), 3 CloudWatch alarms
  - container image pushed to ECR; code package goes to the SAM managed bucket (stack aws-sam-cli-managed-default, exists)
Changes nothing else; deletes nothing. Starting position LATEST: the existing documents are not in the stream,
queue them with:  python3 backfill.py --apply   (after step 2).
TEXT
  echo
  echo "Local checks:"
  if [ -n "$LINT" ]; then
    for t in template.yaml documents-table-with-stream.yaml ecr.yaml; do
      if "$LINT" "$t" >/dev/null 2>&1; then echo "  cfn-lint ok  $t"; else echo "  cfn-lint FAILS  $t"; ok=0; fi
    done
  else echo "  cfn-lint not installed (python3 -m venv .venv-lint && .venv-lint/bin/pip install -r requirements-lint.txt)"; fi
  if [ -n "$SAM" ]; then
    if "$SAM" validate --lint -t template.yaml >/dev/null 2>&1; then echo "  sam validate --lint ok"; else echo "  sam validate --lint FAILS"; ok=0; fi
  fi
  command -v docker >/dev/null && docker info >/dev/null 2>&1 && echo "  docker daemon ok" || { echo "  docker daemon NOT running (needed for step 2)"; ok=0; }
  echo
  echo "Backfill estimate (dry run, reads both tables only):"
  if out=$("$PY" backfill.py 2>&1); then echo "$out" | sed 's/^/  /'; else echo "$out" | tail -3 | sed 's/^/  /'; echo "  backfill dry run FAILED (credentials?)"; ok=0; fi
  echo
  [ "$ok" = 1 ] && echo "(--plan: all checks passed, nothing was created)" || echo "(--plan: see MISSING/EXISTS/FAILS above; nothing was created)"
}

step_stream() {
  [ -z "$(stream_arn)" ] || { echo "The stream is already on: $(stream_arn)"; exit 0; }
  echo "Updates stack $TABLES_STACK with documents-table-with-stream.yaml (enables the stream, nothing else)."
  # --tags must be repeated: `deploy` without it clears the stack tags (and so the table's tag) on update
  aws cloudformation deploy --stack-name "$TABLES_STACK" --template-file documents-table-with-stream.yaml \
    --tags project=wonderfulkb --no-execute-changeset --no-fail-on-empty-changeset
  local cs; cs=$(aws cloudformation list-change-sets --stack-name "$TABLES_STACK" --query 'Summaries[0].ChangeSetName' --output text)
  aws cloudformation describe-change-set --stack-name "$TABLES_STACK" --change-set-name "$cs" \
    --query 'Changes[].ResourceChange.{Action:Action,Resource:LogicalResourceId,Replacement:Replacement,Details:Details[].Target.Attribute}' --output json
  echo "Replacement must be False. If it is not, cancel and delete the change set $cs."
  confirm enable-stream
  aws cloudformation execute-change-set --stack-name "$TABLES_STACK" --change-set-name "$cs"
  aws cloudformation wait stack-update-complete --stack-name "$TABLES_STACK"
  echo "Stream: $(stream_arn)"
}

step_trigger() {
  local stream; stream=$(stream_arn)
  [ -n "$stream" ] || { echo "The stream is off. Run ./deploy.sh stream first." >&2; exit 1; }
  [ -n "$SAM" ] || { echo "SAM CLI missing (python3 -m venv .venv-lint && .venv-lint/bin/pip install -r requirements-lint.txt)." >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo "Docker daemon is not running." >&2; exit 1; }
  echo "Creates ECR repository + stack $TRIGGER_STACK (see --plan). Stream: $stream"
  confirm deploy-trigger
  aws cloudformation deploy --stack-name "$ECR_STACK" --template-file ecr.yaml --no-fail-on-empty-changeset \
    --tags project=wonderfulkb component=trigger
  local repo; repo=$(aws cloudformation describe-stacks --stack-name "$ECR_STACK" --query 'Stacks[0].Outputs[?OutputKey==`RepositoryUri`].OutputValue' --output text)
  ./build.sh
  "$SAM" build -t template.yaml
  local key; key=$(kms_arn)
  [ -n "$key" ] || { echo "KMS alias/wonderfulkb-signatures not found." >&2; exit 1; }
  local params=("StreamArn=$stream" "SignatureKmsKeyArn=$key")
  for p in MaxConcurrency BedrockRpm WorkerMemory AlarmTopicArn WonderfulWebhookSecretName; do
    [ -z "${!p:-}" ] || params+=("$p=${!p}")
  done
  aws ecr get-login-password | docker login --username AWS --password-stdin "${repo%%/*}" >/dev/null
  "$SAM" deploy --stack-name "$TRIGGER_STACK" --capabilities CAPABILITY_NAMED_IAM --resolve-s3 \
    --image-repository "$repo" --tags project=wonderfulkb component=trigger \
    --parameter-overrides "${params[@]}" --confirm-changeset --no-fail-on-empty-changeset
  aws cloudformation describe-stacks --stack-name "$TRIGGER_STACK" --query 'Stacks[0].Outputs' --output table
  echo "Next: python3 backfill.py            (dry run)   then   python3 backfill.py --apply"
}

step_rollback() {
  cat <<TEXT
Rollback removes only what this directory created:
  1. stack $TRIGGER_STACK (queues, Lambdas, roles, alarms; messages still queued are lost, rows stay as they are)
  2. stack $ECR_STACK (repository and its images)
  3. stack $TABLES_STACK is updated back to $ORIGINAL_TEMPLATE (the stream is switched off)
Rows in $ANALYSIS_TABLE and objects in S3 are not touched; rows left in 'queued' can be re-queued later with backfill.py.
TEXT
  confirm rollback
  if stack_exists "$TRIGGER_STACK"; then
    aws cloudformation delete-stack --stack-name "$TRIGGER_STACK"; aws cloudformation wait stack-delete-complete --stack-name "$TRIGGER_STACK"
  fi
  if stack_exists "$ECR_STACK"; then
    aws cloudformation delete-stack --stack-name "$ECR_STACK"; aws cloudformation wait stack-delete-complete --stack-name "$ECR_STACK"
  fi
  if [ -n "$(stream_arn)" ]; then
    aws cloudformation deploy --stack-name "$TABLES_STACK" --template-file "$ORIGINAL_TEMPLATE" --tags project=wonderfulkb --no-fail-on-empty-changeset
  fi
  echo "Done."
}

case "${1:-}" in
  --plan) plan ;;
  stream) step_stream ;;
  trigger) step_trigger ;;
  rollback) step_rollback ;;
  *) sed -n 2,12p "$0"; exit 1 ;;
esac
