#!/usr/bin/env bash
# End-to-end check of the deployed trigger with ONE new document under a new test case (nothing is cleaned up).
#   upload via ingest -> stream -> row `queued` -> worker -> `completed`; then the same upload again (duplicate: nothing starts).
# Reads the ingest API key from Secrets Manager into a header file (never printed). Run only after ./deploy.sh trigger.
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_PROFILE="${AWS_PROFILE:-hackathon}" AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1
STAMP=$(date +%Y%m%d%H%M%S)
CASE_ID="trigger-test-$STAMP"
ANALYSIS=wonderfulkb-uw-document-analysis
BASE_URL="${BASE_URL:-}"
if [ -z "$BASE_URL" ]; then
  arn=$(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='wonderfulkb-ingest'].ServiceArn | [0]" --output text)
  BASE_URL="https://$(aws apprunner describe-service --service-arn "$arn" --query Service.ServiceUrl --output text)"
fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
printf 'x-api-key: %s\n' "$(aws secretsmanager get-secret-value --secret-id wonderfulkb/ingest-api-key --query SecretString --output text)" > "$TMP/auth"
chmod 600 "$TMP/auth"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
"$PY" - "$TMP/test.pdf" "$STAMP" <<'PYEOF'
import sys, pymupdf   # a unique, synthetic, text-layer PDF: its hash is new, so the dedup step cannot reuse another case
doc = pymupdf.open()
for n in (1, 2):
    page = doc.new_page()
    page.insert_text((60, 90), f"Testovaci dokument triggeru {sys.argv[2]}, strana {n}", fontsize=12)
    page.insert_text((60, 120), "Smlouva o uveru c. TEST-" + sys.argv[2] + ". Dluznik se zavazuje splacet dohodnute splatky.", fontsize=10)
    page.insert_text((60, 140), "Syntheticka data pro overeni automatickeho zpracovani po nahrani.", fontsize=10)
doc.save(sys.argv[1])
PYEOF
echo "case $CASE_ID, ingest $BASE_URL"
aws dynamodb put-item --table-name wonderfulkb-uw-cases --item \
  "{\"case_id\":{\"S\":\"$CASE_ID\"},\"client_id\":{\"S\":\"trigger-test\"},\"status\":{\"S\":\"open\"},\"created_at\":{\"S\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}"
upload() { curl -s -w '\nHTTP %{http_code}\n' -X POST "$BASE_URL/v1/cases/$CASE_ID/documents" -H "@$TMP/auth" -F "files=@$TMP/test.pdf;type=application/pdf" -F uploaded_by=trigger-e2e; }
echo "--- upload 1"; out=$(upload); echo "$out"
DOC=$(echo "$out" | head -n1 | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["documents"][0]["document_id"])' 2>/dev/null || true)
[ -n "$DOC" ] || DOC=$(echo "$out" | "$PY" -c 'import re,sys; print(re.search(r"\"document_id\": ?\"([^\"]+)\"", sys.stdin.read()).group(1))')
echo "document_id $DOC"
row() { aws dynamodb get-item --table-name "$ANALYSIS" --consistent-read --key "{\"case_id\":{\"S\":\"$CASE_ID\"},\"document_id\":{\"S\":\"$DOC\"}}" --query 'Item.processing_status.S' --output text 2>/dev/null; }
last=""; for i in $(seq 1 100); do
  s=$(row); [ "$s" = "$last" ] || { echo "$(date +%H:%M:%S) status: ${s:-<no row>}"; last=$s; }
  case "$s" in completed|partial|failed) break;; esac; sleep 15
done
echo "--- final row"
aws dynamodb get-item --table-name "$ANALYSIS" --key "{\"case_id\":{\"S\":\"$CASE_ID\"},\"document_id\":{\"S\":\"$DOC\"}}" --output json |
  "$PY" -c 'import json,sys; i=json.load(sys.stdin)["Item"]; print(json.dumps({k:(list(v.values())[0]) for k,v in i.items()}, ensure_ascii=False, indent=1))'
echo "--- objects"
aws s3 ls "s3://wonderfulkb-raw-document-storage/cases/$CASE_ID/" --recursive | awk '{print $1, $2, $3, $4}'
echo "--- upload 2 (same file: must be a duplicate and start nothing)"; upload
sleep 20; echo "status after duplicate: $(row)"
echo "--- queues"
for q in wonderfulkb-trigger-documents wonderfulkb-trigger-documents-dlq; do
  aws sqs get-queue-attributes --queue-url "$(aws sqs get-queue-url --queue-name $q --query QueueUrl --output text)" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible --query Attributes --output text | sed "s/^/$q: /"
done
echo "test case kept: $CASE_ID / $DOC"
