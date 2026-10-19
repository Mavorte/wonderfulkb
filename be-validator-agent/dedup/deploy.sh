#!/usr/bin/env bash
# Plán (a po souhlasu uživatele nasazení) indexu obsahových hashů pro dedup napříč případy.
#   ./deploy.sh --plan    jen ČTE: ověří účet a stav, vypíše, co by se vytvořilo a co se musí nasadit dál. Nic nevytvoří.
#   ./deploy.sh           po napsání slova "deploy" vytvoří stack wonderfulkb-content-hashes (jen tabulka).
# Backfill, nasazení ingestu a agent API jsou samostatné kroky a tento skript je NEDĚLÁ; viz README.md.
# NESPOUŠTĚT bez souhlasu uživatele (sdílený účet <ACCOUNT_ID>, eu-central-1).
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE="${AWS_PROFILE:-hackathon}" AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1
STACK="${STACK:-wonderfulkb-content-hashes}"
TABLE=wonderfulkb-uw-content-hashes
MODE="${1:-}"
case "$MODE" in ""|--plan) ;; *) echo "použití: $0 [--plan]" >&2; exit 2;; esac

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
[ "$ACCOUNT" = "<ACCOUNT_ID>" ] || { echo "Špatný účet $ACCOUNT (čekám <ACCOUNT_ID>)." >&2; exit 1; }

state() { # jen čtení; vypíše stav zdroje
  if "$@" >/dev/null 2>&1; then echo "existuje"; else echo "neexistuje"; fi
}
echo "Stav v $ACCOUNT / $AWS_REGION (jen čtení):"
echo "  tabulka $TABLE:                    $(state aws dynamodb describe-table --table-name "$TABLE")"
echo "  stack $STACK:                      $(state aws cloudformation describe-stacks --stack-name "$STACK")"
echo "  tabulka wonderfulkb-uw-documents:  $(state aws dynamodb describe-table --table-name wonderfulkb-uw-documents)"
echo "  tabulka wonderfulkb-uw-document-analysis: $(state aws dynamodb describe-table --table-name wonderfulkb-uw-document-analysis)"
if aws dynamodb describe-table --table-name wonderfulkb-uw-documents >/dev/null 2>&1; then
  echo "  dokumentů k backfillu:             $(aws dynamodb scan --table-name wonderfulkb-uw-documents --select COUNT --query Count --output text)"
fi

cat <<PLAN

Plán (nic z toho se v režimu --plan neprovádí):
  1. [tento skript] CloudFormation stack $STACK: DynamoDB tabulka $TABLE
     PK sha256 (S), SK case_document (S) = "<case_id>#<document_id>", on-demand, tag project=wonderfulkb.
     Atributy: case_id, document_id, label, registered_at. Žádný jiný zdroj, žádné IAM, žádná Lambda.
  2. [ručně] backfill:   .venv/bin/python -I -m dedup.backfill           (výpis, nic nezapíše)
                         .venv/bin/python -I -m dedup.backfill --apply   (zapíše)
  3. [ručně, IAM] role potřebují přístup k tabulce (arn:aws:dynamodb:$AWS_REGION:$ACCOUNT:table/$TABLE):
       ingest (role wonderfulkb-ingest-instance):  dynamodb:Query, dynamodb:UpdateItem
       pipeline / trigger worker:                  dynamodb:Query, dynamodb:UpdateItem (a čtení wonderfulkb-uw-document-analysis, S3 Vectors GetVectors/PutVectors)
       agent API (wonderfulkb-agent-api-lambda):   dynamodb:Query (řeší api/template.yaml) a GetItem na wonderfulkb-uw-documents
  4. [ručně, po souhlasu] nasazení ingestu (nový obraz) a agent API (api/deploy.sh); bez toho dedup v běžícím systému nic nedělá.
Nic z tohoto skriptu nemění ingest, API, pipeline ani jiné tabulky.
PLAN
[ "$MODE" = "--plan" ] && { echo "(--plan: nic se nevytvořilo)"; exit 0; }

read -r -p 'Pro vytvoření tabulky napiš "deploy": ' answer
[ "$answer" = "deploy" ] || { echo "Zrušeno."; exit 1; }
aws cloudformation deploy --stack-name "$STACK" --template-file template.yaml --no-fail-on-empty-changeset \
  --tags project=wonderfulkb
echo "Hotovo. Další kroky 2 až 4 viz README.md."
