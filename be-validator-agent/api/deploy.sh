#!/usr/bin/env bash
# Nasazení stacku wonderfulkb-agent-api (Lambda + HTTP API). NESPOUŠTĚT bez souhlasu uživatele.
# Potřebuje: aws sso login --profile hackathon, SAM CLI (pip install aws-sam-cli), Python 3.14 na PATH.
#   ./deploy.sh            vypíše, co vytvoří, a čeká na potvrzení (napsat "deploy"); pak sam deploy ukáže ještě changeset
#   ./deploy.sh --plan     jen výpis a kontroly, nic se nevytvoří ani neprobíhá build
# Volitelné proměnné: ARTIFACT_BUCKET (existující bucket pro balíček; jinak SAM založí spravovaný stack
#   aws-sam-cli-managed-default), CASES_TABLE (viz template.yaml), STACK (výchozí wonderfulkb-agent-api).
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE="${AWS_PROFILE:-hackathon}" AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1
export SAM_CLI_TELEMETRY=0
STACK="${STACK:-wonderfulkb-agent-api}"
CASES_TABLE="${CASES_TABLE:-wonderfulkb-uw-cases}"
# DOČASNĚ true do migrace starých čitelných výřezů (audit V3, viz README "Přechod z crop_url"); po migraci false.
LEGACY_PLAIN_CROP_URL="${LEGACY_PLAIN_CROP_URL:-true}"
ANALYSIS_TABLE=wonderfulkb-uw-document-analysis
RAW_BUCKET=wonderfulkb-raw-document-storage
VECTOR_BUCKET=wonderfulkb-vectors
SECRET=wonderfulkb/ingest-api-key
KMS_ALIAS=alias/wonderfulkb-signatures
KMS_KEY_ID=<KMS_KEY_ID>   # musí odpovídat parametru SignatureKmsKeyId v template.yaml

command -v sam >/dev/null || { echo "Chybí SAM CLI (pip install aws-sam-cli)." >&2; exit 1; }
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
[ "$ACCOUNT" = "<ACCOUNT_ID>" ] || { echo "Špatný účet $ACCOUNT (čekám <ACCOUNT_ID>)." >&2; exit 1; }

# Kontroly závislostí (jen existence, žádné hodnoty).
ok=1
chk() { if "${@:2}" >/dev/null 2>&1; then echo "  ok      $1"; else echo "  CHYBÍ   $1"; ok=0; fi; }
echo "Kontrola závislostí v $ACCOUNT / $AWS_REGION:"
chk "DynamoDB $ANALYSIS_TABLE" aws dynamodb describe-table --table-name "$ANALYSIS_TABLE"
chk "S3 bucket $RAW_BUCKET" aws s3api head-bucket --bucket "$RAW_BUCKET"
for i in text image signatures; do
  chk "S3 Vectors index wonderfulkb-$i" aws s3vectors get-index --vector-bucket-name "$VECTOR_BUCKET" --index-name "wonderfulkb-$i"
done
chk "Secrets Manager $SECRET" aws secretsmanager describe-secret --secret-id "$SECRET"
chk "KMS klíč $KMS_ALIAS (odkrytí podpisů)" aws kms describe-key --key-id "$KMS_ALIAS"
if ACTUAL_KEY_ID=$(aws kms describe-key --key-id "$KMS_ALIAS" --query KeyMetadata.KeyId --output text 2>/dev/null); then
  [ "$ACTUAL_KEY_ID" = "$KMS_KEY_ID" ] && echo "  ok      alias $KMS_ALIAS míří na klíč $KMS_KEY_ID (podle šablony)" \
    || { echo "  CHYBÍ   alias $KMS_ALIAS míří na jiný klíč než SignatureKmsKeyId v šabloně ($KMS_KEY_ID)"; ok=0; }
fi
[ -z "$CASES_TABLE" ] || chk "DynamoDB $CASES_TABLE" aws dynamodb describe-table --table-name "$CASES_TABLE"
[ "$ok" = 1 ] || { echo "Chybí závislosti, nasazení by selhalo za běhu. Končím." >&2; exit 1; }

if [ -n "${ARTIFACT_BUCKET:-}" ]; then ARTIFACT_DESC="do bucketu $ARTIFACT_BUCKET"
else ARTIFACT_DESC="do spravovaného bucketu SAM (stack aws-sam-cli-managed-default, založí se, pokud neexistuje)"; fi
if aws cloudformation describe-stacks --stack-name "$STACK" >/dev/null 2>&1; then MODE="AKTUALIZACE existujícího stacku"; else MODE="NOVÝ stack"; fi
cat <<PLAN

Nasazení: $MODE '$STACK' (účet $ACCOUNT, $AWS_REGION, tag project=wonderfulkb)
Vytvoří / změní:
  - Lambda wonderfulkb-agent-api (python3.14, arm64, 512 MB, 20 s), kód z tohoto adresáře + boto3>=1.40
  - IAM role wonderfulkb-agent-api-lambda (jen čtení: $ANALYSIS_TABLE GetItem/Query;
    s3:GetObject na $RAW_BUCKET/cases/*/analysis/*; s3vectors GetVectors/QueryVectors na 3 indexy v $VECTOR_BUCKET;
    GetSecretValue na $SECRET; zápis do vlastní log skupiny)${CASES_TABLE:+; GetItem na $CASES_TABLE}
    + odkrytí podpisů: kms:Decrypt jen na klíč $KMS_KEY_ID ($KMS_ALIAS) a jen s kontextem právě case_id, document_id,
      signature_id (žádné GenerateDataKey/Encrypt; zápis šifrovaných výřezů zůstává u pipeline). s3:GetObject se nemění
      (cases/*/analysis/* už pokrývá signatures/*)
  - proměnné Lambdy: PRIVACY_KMS_KEY_ID=$KMS_ALIAS, LEGACY_PLAIN_CROP_URL=$LEGACY_PLAIN_CROP_URL (dočasně do migrace),
    CROP_URL_COMPAT=${CROP_URL_COMPAT:-false}
  - Odpověď volání 3: přibude preview_url, reveal_path, crop_available a cesta GET …/signatures/{signature_id}/image
    (odkrytí, audit do logu Lambdy); crop_url zůstane jen u starých čitelných výřezů, dokud LEGACY_PLAIN_CROP_URL=true.
    Chybějící x-api-key vrací 401 (dříve 403), špatný klíč dál 403. Viz README, "Přechod z crop_url".
  - dedup: role navíc smí dynamodb:Query na wonderfulkb-uw-content-hashes a dynamodb:GetItem na wonderfulkb-uw-documents (jen sha256);
    tabulka hashů nemusí existovat, API pak pole duplicate_of a duplicate_relevant vynechá (parametr ContentHashesTable="" funkci vypne)
  - CloudWatch log skupina /aws/lambda/wonderfulkb-agent-api (14 dní)
  - API Gateway HTTP API, stage v1, trasy GET /{proxy+} a GET /healthz, limit 10 req/s (burst 20)
  - balíček kódu: $ARTIFACT_DESC
Nemění ani nemaže nic jiného. API klíč se nenastavuje; Lambda ho čte za běhu ze Secrets Manageru.
PLAN
[ "${1:-}" = "--plan" ] && { echo "(--plan: nic se nevytvořilo)"; exit 0; }

read -r -p 'Pro pokračování napiš "deploy": ' answer
[ "$answer" = "deploy" ] || { echo "Zrušeno."; exit 1; }

sam build
OVERRIDES=()
[ -z "$CASES_TABLE" ] || OVERRIDES+=("CasesTable=$CASES_TABLE")
OVERRIDES+=("LegacyPlainCropUrl=$LEGACY_PLAIN_CROP_URL")
[ -z "${CROP_URL_COMPAT:-}" ] || OVERRIDES+=("CropUrlCompat=$CROP_URL_COMPAT")   # přechod z crop_url, viz README
PARAM_ARGS=()
[ "${#OVERRIDES[@]}" = 0 ] || PARAM_ARGS=(--parameter-overrides "${OVERRIDES[@]}")
S3_ARGS=(--resolve-s3)
[ -z "${ARTIFACT_BUCKET:-}" ] || S3_ARGS=(--s3-bucket "$ARTIFACT_BUCKET" --s3-prefix wonderfulkb-agent-api)
sam deploy --stack-name "$STACK" --capabilities CAPABILITY_NAMED_IAM "${S3_ARGS[@]}" \
  --tags project=wonderfulkb component=agent-api ${PARAM_ARGS[@]+"${PARAM_ARGS[@]}"} \
  --confirm-changeset --no-fail-on-empty-changeset

aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].Outputs' --output table
echo "Ověření: python3 verify_deployed.py <ApiUrl> <case_id> <document_id>   (viz README, sekce Nasazení)"
