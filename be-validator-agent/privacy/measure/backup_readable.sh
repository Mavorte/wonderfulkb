#!/usr/bin/env bash
# Záloha ČITELNÝCH dat před jejich pozdějším smazáním (rozhodnutí uživatele: zálohovat). Postup: be-validator-agent/docs/validator-agent-privacy.md, část 8a.
#
#   backup_readable.sh --plan      výchozí. Jen ČTE (list-object-versions): zapíše seznam klíčů a VersionId do
#                                  $PLAN_DIR a vypíše počty a velikost. Nic nekopíruje, nic nezapisuje do AWS.
#   backup_readable.sh --run       zkopíruje každou verzi do $BACKUP_BUCKET/$BACKUP_PREFIX/<klíč> a zašifruje ji JINÝM
#                                  KMS klíčem než podpisy ($BACKUP_KMS_KEY_ID). Vyžaduje BACKUP_CONFIRM=yes.
#   backup_readable.sh --verify    porovná zálohu se seznamem (existence, velikost, šifrování klíčem zálohy); s --deep
#                                  i SHA-256 obsahu zdroje a kopie.
#
# NESPOUŠTĚT bez schválení uživatele: --run potřebuje nový KMS klíč (alias/wonderfulkb-backup) a cíl zálohy, které
# schvaluje uživatel. Skript žádný klíč ani bucket nevytváří. NIKDY nic nemaže (žádné delete-*). Smazání čitelných
# verzí je samostatný pozdější krok.
#
# Prostředí: AWS_PROFILE=hackathon (nebo exportovaná přihlášení), region eu-central-1.
#   SRC_BUCKET        výchozí wonderfulkb-raw-document-storage
#   BACKUP_BUCKET     výchozí stejný bucket; MUSÍ se lišit prefixem od cases/ (skript to hlídá). Bezpečnější je samostatný bucket
#   BACKUP_PREFIX     výchozí backup-readable/<datum>   (nesmí začínat "cases/")
#   BACKUP_KMS_KEY_ID nutné pro --run a --verify; musí být jiný než klíč podpisů (alias/wonderfulkb-signatures)
#   PLAN_DIR          výchozí ./backup-plan (mimo repozitář)
#   INCLUDE_ZIPS=1    zahrne i ZIP balíky v cases/*.zip (synteticke_dokumenty_20_pripadu.zip 33 MB, codex-tmp.zip 446 MB)
set -euo pipefail

MODE="plan"; DEEP=0
for a in "$@"; do
  case "$a" in
    --plan) MODE=plan;; --run) MODE=run;; --verify) MODE=verify;; --deep) DEEP=1;;
    -h|--help) sed -n 2,24p "$0"; exit 0;;
    *) echo "neznámý argument: $a" >&2; exit 2;;
  esac
done

: "${AWS_PROFILE:=hackathon}"; export AWS_PROFILE AWS_DEFAULT_REGION=eu-central-1
SRC_BUCKET="${SRC_BUCKET:-wonderfulkb-raw-document-storage}"
BACKUP_BUCKET="${BACKUP_BUCKET:-$SRC_BUCKET}"
BACKUP_PREFIX="${BACKUP_PREFIX:-backup-readable/$(date -u +%Y-%m-%d)}"
PLAN_DIR="${PLAN_DIR:-./backup-plan}"
SIG_KEY_ALIAS="alias/wonderfulkb-signatures"
PLAN_TSV="$PLAN_DIR/versions.tsv"      # klíč<TAB>VersionId<TAB>velikost<TAB>ETag<TAB>IsLatest<TAB>skupina

case "$BACKUP_PREFIX" in cases/*|cases) echo "BACKUP_PREFIX nesmí ležet pod cases/" >&2; exit 2;; esac
mkdir -p "$PLAN_DIR"

plan() {
  echo "Čtu verze objektů v s3://$SRC_BUCKET/cases/ (jen výpis, žádný zápis)..."
  aws s3api list-object-versions --bucket "$SRC_BUCKET" --prefix cases/ --output json > "$PLAN_DIR/all-versions.json"
  INCLUDE_ZIPS="${INCLUDE_ZIPS:-0}" python3 - "$PLAN_DIR" <<'PY'
import json, os, re, sys
d = sys.argv[1]
doc = json.load(open(f"{d}/all-versions.json"))
groups = [  # (skupina, regulární výraz klíče)
    ("original_pdf", r"^cases/[^/]+/original/[^/]+\.pdf$"),
    ("page_png",     r"^cases/[^/]+/analysis/[^/]+/pages/\d+\.png$"),
    ("original_page_png", r"^cases/[^/]+/original-pages/[^/]+/\d+\.png$"),
    ("crop_png",     r"^cases/[^/]+/analysis/[^/]+/signatures/sig_\d+\.png$"),   # jen čitelné; .png.enc a .preview.png ne
]
if os.environ.get("INCLUDE_ZIPS") == "1":
    groups.append(("zip_bundle", r"^cases/[^/]+\.zip$"))
rows = []
for v in doc.get("Versions", []):
    for g, rx in groups:
        if re.match(rx, v["Key"]):
            rows.append((v["Key"], v["VersionId"], v["Size"], v["ETag"].strip('"'), v["IsLatest"], g))
rows.sort()
with open(f"{d}/versions.tsv", "w") as f:
    for r in rows:
        f.write("\t".join(str(x) for x in r) + "\n")
markers = [m for m in doc.get("DeleteMarkers", []) if any(re.match(rx, m["Key"]) for _, rx in groups)]
by = {}
for r in rows:
    c = by.setdefault(r[5], [0, 0, 0]); c[0] += 1; c[1] += r[2]; c[2] += 0 if r[4] else 1
print(f"{'skupina':14} {'verzí':>6} {'MB':>9} {'z toho starších':>16}")
for g, (n, s, old) in sorted(by.items()):
    print(f"{g:14} {n:6d} {s/1e6:9.1f} {old:16d}")
print(f"celkem verzí {len(rows)}, {sum(r[2] for r in rows)/1e6:.1f} MB; delete markerů u těchto klíčů: {len(markers)}")
print(f"seznam: {d}/versions.tsv (klíč, VersionId, velikost, ETag, IsLatest, skupina)")
PY
  echo "Cíl zálohy (jen plán): s3://$BACKUP_BUCKET/$BACKUP_PREFIX/<klíč>  šifrování: SSE-KMS, klíč ${BACKUP_KMS_KEY_ID:-<NENASTAVEN>}"
  if [ -z "${BACKUP_KMS_KEY_ID:-}" ]; then echo "POZOR: BACKUP_KMS_KEY_ID není nastaven; pro --run je potřeba klíč schválený uživatelem (jiný než $SIG_KEY_ALIAS)."; fi
}

need_key() {
  [ -n "${BACKUP_KMS_KEY_ID:-}" ] || { echo "BACKUP_KMS_KEY_ID není nastaven" >&2; exit 2; }
  local sig_arn bk_arn
  sig_arn=$(aws kms describe-key --key-id "$SIG_KEY_ALIAS" --query KeyMetadata.Arn --output text)
  bk_arn=$(aws kms describe-key --key-id "$BACKUP_KMS_KEY_ID" --query KeyMetadata.Arn --output text)
  [ "$sig_arn" != "$bk_arn" ] || { echo "klíč zálohy musí být JINÝ než klíč podpisů" >&2; exit 2; }
}

run() {
  [ "${BACKUP_CONFIRM:-}" = "yes" ] || { echo "--run vyžaduje BACKUP_CONFIRM=yes (po schválení uživatelem)" >&2; exit 2; }
  need_key
  [ -s "$PLAN_TSV" ] || plan
  local n=0
  while IFS=$'\t' read -r key vid size etag latest grp; do
    # každá verze dostane vlastní podklíč; VersionId zdroje je v klíči i v metadatech kopie
    dest="$BACKUP_PREFIX/$key.v-$vid"
    if aws s3api head-object --bucket "$BACKUP_BUCKET" --key "$dest" >/dev/null 2>&1; then continue; fi   # idempotentní
    aws s3api copy-object --bucket "$BACKUP_BUCKET" --key "$dest" \
      --copy-source "$SRC_BUCKET/$key?versionId=$vid" \
      --server-side-encryption aws:kms --ssekms-key-id "$BACKUP_KMS_KEY_ID" \
      --metadata-directive REPLACE --metadata "src-key=$(printf %s "$key" | tr -c 'A-Za-z0-9/_.-' '_'),src-version=$vid,project=wonderfulkb" \
      --tagging "project=wonderfulkb" --output text --query CopyObjectResult.ETag >/dev/null
    n=$((n+1))
  done < "$PLAN_TSV"
  echo "zkopírováno verzí: $n (již existující přeskočeny)"
  cp "$PLAN_TSV" "$PLAN_DIR/versions.copied.tsv"
}

verify() {
  need_key
  [ -s "$PLAN_TSV" ] || { echo "chybí $PLAN_TSV (spusť --plan)" >&2; exit 2; }
  local bad=0 total=0 bk_arn
  bk_arn=$(aws kms describe-key --key-id "$BACKUP_KMS_KEY_ID" --query KeyMetadata.Arn --output text)
  while IFS=$'\t' read -r key vid size etag latest grp; do
    total=$((total+1)); dest="$BACKUP_PREFIX/$key.v-$vid"
    read -r csize enc kid < <(aws s3api head-object --bucket "$BACKUP_BUCKET" --key "$dest" \
      --query '[ContentLength,ServerSideEncryption,SSEKMSKeyId]' --output text 2>/dev/null || echo "- - -")
    if [ "$csize" != "$size" ] || [ "$enc" != "aws:kms" ] || [ "$kid" != "$bk_arn" ]; then
      echo "CHYBA: $key ($vid): velikost/šifrování nesedí"; bad=$((bad+1)); continue
    fi
    if [ "$DEEP" = 1 ]; then
      a=$(aws s3api get-object --bucket "$SRC_BUCKET" --key "$key" --version-id "$vid" /dev/stdout 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
      b=$(aws s3api get-object --bucket "$BACKUP_BUCKET" --key "$dest" /dev/stdout 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
      [ "$a" = "$b" ] || { echo "CHYBA: $key ($vid): obsah se liší"; bad=$((bad+1)); }
    fi
  done < "$PLAN_TSV"
  echo "zkontrolováno $total verzí, chyb: $bad"
  [ "$bad" = 0 ]
}

case "$MODE" in plan) plan;; run) run;; verify) verify;; esac
