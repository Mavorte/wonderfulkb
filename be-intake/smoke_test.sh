#!/usr/bin/env bash
# Smoke test sluzby wonderfulkb-ingest. Pouziti: BASE_URL=https://... API_KEY=... ./smoke_test.sh
# Vytvori jednu testovaci polozku v wonderfulkb-uw-cases a na konci (i pri chybe) uklidi vse, co test vytvoril.
set -u
: "${BASE_URL:?nastav BASE_URL}" "${API_KEY:?nastav API_KEY}"
BASE_URL="${BASE_URL%/}"
export PATH=/usr/local/bin:$PATH AWS_PROFILE=hackathon AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1
BUCKET=wonderfulkb-raw-document-storage
CASE_ID="wonderfulkb-smoketest-$(date +%s)"
CASE2="$CASE_ID-b"   # druhy case pro duplicitu napric pripady (also_in)
SAMPLES=/Users/kuku/Desktop/hackaton_kb/docs/vzorove-dokumenty/solom-rec
PDFS=("$SAMPLES/0_Form_Smlouva.pdf" "$SAMPLES/01_Form_VOP.pdf" "$SAMPLES/3_Form_Vinkulace_poj.pdf")
URL="$BASE_URL/v1/cases/$CASE_ID/documents"
TMP=$(mktemp -d); PASS=0; FAILS=0; CREATED=0
echo "API_KEY=**** (${#API_KEY} znaku), BASE_URL=$BASE_URL, case=$CASE_ID"
printf 'x-api-key: %s\n' "$API_KEY" > "$TMP/auth"   # hlavicka v souboru, klic se neobjevi v logu ani v argumentech curl

cleanup() {
  local rc=$?
  trap - EXIT
  echo "--- uklid"
  [ "$CREATED" = 1 ] && for C in "$CASE_ID" "$CASE2"; do
    aws dynamodb query --table-name wonderfulkb-uw-documents --key-condition-expression 'case_id = :c' \
      --expression-attribute-values "{\":c\":{\"S\":\"$C\"}}" --projection-expression document_id \
      --query 'Items[].document_id.S' --output text | tr '\t' '\n' | grep . | while read -r id; do
        aws dynamodb delete-item --table-name wonderfulkb-uw-documents \
          --key "{\"case_id\":{\"S\":\"$C\"},\"document_id\":{\"S\":\"$id\"}}"
      done
    aws s3api list-object-versions --bucket "$BUCKET" --prefix "cases/$C/" --output json > "$TMP/versions.json"
    python3 - "$TMP/versions.json" > "$TMP/delete.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
objs = [{"Key": v["Key"], "VersionId": v["VersionId"]} for k in ("Versions", "DeleteMarkers") for v in d.get(k) or []]
print(json.dumps({"Objects": objs, "Quiet": True}))
EOF
    grep -q '"Key"' "$TMP/delete.json" && aws s3api delete-objects --bucket "$BUCKET" --delete "file://$TMP/delete.json" >/dev/null
    aws dynamodb delete-item --table-name wonderfulkb-uw-cases --key "{\"case_id\":{\"S\":\"$C\"}}"
    echo "smazano ($C): dokumenty, S3 verze, testovaci case"
  done
  for sha in $(cat "$TMP/shas" 2>/dev/null); do for C in "$CASE_ID" "$CASE2"; do   # index hashu: jen radky testovacich case
    aws dynamodb query --table-name wonderfulkb-uw-content-hashes --key-condition-expression 'sha256 = :s' \
      --expression-attribute-values "{\":s\":{\"S\":\"$sha\"}}" --query 'Items[].case_document.S' --output text \
      | tr '\t' '\n' | grep "^$C#" | while read -r cd; do
        aws dynamodb delete-item --table-name wonderfulkb-uw-content-hashes \
          --key "{\"sha256\":{\"S\":\"$sha\"},\"case_document\":{\"S\":\"$cd\"}}"
      done
  done; done
  rm -rf "$TMP"
  echo "=== PASS: $PASS, FAIL: $FAILS"
  [ "$FAILS" -gt 0 ] && rc=1
  exit "$rc"
}
trap cleanup EXIT
# hashe vsech nahravanych vzorku: ingest je zapisuje do indexu wonderfulkb-uw-content-hashes, uklid maze jen radky testovacich case
shasum -a 256 "${PDFS[@]}" "$SAMPLES/4_Form_Ručení.pdf" | cut -d' ' -f1 > "$TMP/shas"

# --- pomocne funkce ---
check() { if [ "$2" = 1 ]; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1 ${3:-}"; FAILS=$((FAILS+1)); fi; }
# req <metoda> <url> [curl args...]: do $CODE ulozi HTTP kod, telo je v $TMP/body
req() { local m=$1 u=$2; shift 2; CODE=$(curl -s -o "$TMP/body" -w '%{http_code}' -X "$m" "$u" "$@"); }
authed() { req "$@" -H "@$TMP/auth"; }
# py <vyraz>: vyhodnoti vyraz nad JSONem z posledni odpovedi (promenna d), vypise 1/0
py() { python3 -c 'import json,sys; d=json.load(open(sys.argv[2])); print(1 if eval(sys.argv[1]) else 0)' "$1" "$TMP/body" 2>/dev/null || echo 0; }
code_is() { check "$1" "$([ "$CODE" = "$2" ] && echo 1 || echo 0)" "(HTTP $CODE, ocekavano $2)"; }

# --- 0. testovaci case (jedina zapsana polozka v cizi tabulce) ---
aws dynamodb put-item --table-name wonderfulkb-uw-cases --item \
  "{\"case_id\":{\"S\":\"$CASE_ID\"},\"client_id\":{\"S\":\"smoketest\"},\"status\":{\"S\":\"open\"},\"created_at\":{\"S\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}" \
  && CREATED=1 || { echo "FAIL nelze vytvorit testovaci case"; exit 1; }
aws dynamodb put-item --table-name wonderfulkb-uw-cases --item \
  "{\"case_id\":{\"S\":\"$CASE2\"},\"client_id\":{\"S\":\"smoketest\"},\"status\":{\"S\":\"open\"},\"created_at\":{\"S\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}" \
  || { echo "FAIL nelze vytvorit druhy testovaci case"; exit 1; }

# --- 1. autentizace a chyby ---
req GET "$BASE_URL/healthz";                              code_is "healthz bez klice -> 200" 200
req GET "$URL";                                           code_is "bez x-api-key -> 401" 401
req GET "$URL" -H "x-api-key: spatny-klic";               code_is "spatny klic -> 403" 403
authed GET "$BASE_URL/v1/cases/wonderfulkb-neexistuje-$$/documents"
code_is "neexistujici case -> 404" 404; check "404 ma tvar {error}" "$(py "set(d)=={'error'} and isinstance(d['error'],str)")"

# --- 2. upload 3 PDF najednou ---
F=(); for f in "${PDFS[@]}"; do F+=(-F "files=@$f;type=application/pdf"); done
authed POST "$URL" "${F[@]}" -F "uploaded_by=smoketest"
code_is "upload 3 PDF -> 201" 201
check "3 dokumenty s povinnymi poli a duplicate=false" "$(py "len(d['documents'])==3 and all(set(x)>={'document_id','filename','received_at','content_type','size_bytes'} and x['duplicate'] is False and x['size_bytes']>0 for x in d['documents'])")"
IDS1=$(python3 -c 'import json,sys; print(",".join(sorted(x["document_id"] for x in json.load(open(sys.argv[1]))["documents"])))' "$TMP/body" 2>/dev/null)

authed POST "$URL" "${F[@]}" -F "uploaded_by=smoketest"
code_is "opakovany upload -> 201" 201
IDS2=$(python3 -c 'import json,sys; print(",".join(sorted(x["document_id"] for x in json.load(open(sys.argv[1]))["documents"])))' "$TMP/body" 2>/dev/null)
check "opakovany upload: duplicate=true" "$(py "len(d['documents'])==3 and all(x['duplicate'] is True for x in d['documents'])")"
check "opakovany upload: stejna document_id" "$([ -n "$IDS1" ] && [ "$IDS1" = "$IDS2" ] && echo 1 || echo 0)"

# --- 3. nevalidni vstupy (nic se nesmi zapsat) ---
printf 'toto neni pdf\n' > "$TMP/fake.pdf"; : > "$TMP/empty.pdf"
authed POST "$URL" -F "files=@$TMP/fake.pdf;type=application/pdf";   code_is "text jako .pdf -> 415" 415
authed POST "$URL" -F "files=@$TMP/empty.pdf;type=application/pdf";  code_is "prazdny soubor -> 415" 415

# --- 4. seznam, strankovani, odkazy ---
authed GET "$URL"; code_is "GET seznam -> 200" 200
check "seznam: 3 dokumenty (nic navic se nezapsalo)" "$(py "len(d['documents'])==3 and d['next_token'] is None")"
check "seznam: razeno podle received_at" "$(py "[x['received_at'] for x in d['documents']]==sorted(x['received_at'] for x in d['documents'])")"

authed GET "$URL?limit=2"; code_is "limit=2 -> 200" 200
check "limit=2: 2 dokumenty a next_token" "$(py "len(d['documents'])==2 and bool(d['next_token'])")"
TOKEN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next_token"] or "")' "$TMP/body" 2>/dev/null)
authed GET "$URL" -G --data-urlencode "limit=2" --data-urlencode "next_token=$TOKEN"; code_is "next_token -> 200" 200
check "next_token: zbyva 1 dokument, bez dalsiho tokenu" "$(py "len(d['documents'])==1 and d['next_token'] is None")"

authed GET "$URL?with_urls=true"; code_is "with_urls=true -> 200" 200
check "kazdy dokument ma download_url" "$(py "len(d['documents'])==3 and all(x.get('download_url','').startswith('https://') for x in d['documents'])")"
python3 -c 'import json,sys; print("\n".join(x["download_url"] for x in json.load(open(sys.argv[1]))["documents"]))' "$TMP/body" > "$TMP/urls" 2>/dev/null
OK=0; while read -r u; do
  [ "$(curl -s -o "$TMP/dl" -w '%{http_code}' "$u")" = 200 ] && [ "$(head -c5 "$TMP/dl")" = "%PDF-" ] && OK=$((OK+1))
done < "$TMP/urls"
check "download_url: 3x HTTP 200 a telo zacina %PDF-" "$([ "$OK" = 3 ] && echo 1 || echo 0)" "(ok: $OK/3)"

authed GET "$URL?next_token=not-a-token"; code_is "neplatny next_token -> 400" 400

# --- 5. stejny soubor 2x v jednom pozadavku, neexistujici case s velkym telem ---
R="$SAMPLES/4_Form_Ručení.pdf"
authed POST "$URL" -F "files=@$R;type=application/pdf" -F "files=@$R;type=application/pdf"; code_is "stejny soubor 2x v jednom pozadavku -> 201" 201
check "druhy vyskyt je duplicate, stejne document_id" "$(py "len(d['documents'])==2 and d['documents'][0]['duplicate'] is False and d['documents'][1]['duplicate'] is True and d['documents'][0]['document_id']==d['documents'][1]['document_id']")"
authed GET "$URL"; check "po tom je v case 4 dokumenty" "$(py "len(d['documents'])==4")"
head -c 30000000 /dev/zero | tr '\0' 'x' > "$TMP/big.bin"
START=$(date +%s)
authed POST "$BASE_URL/v1/cases/wonderfulkb-neexistuje-$$/documents" -F "files=@$TMP/big.bin;type=application/pdf"
ELAPSED=$(( $(date +%s) - START ))
check "neexistujici case + 30 MB telo -> 404 hned (${ELAPSED}s)" "$([ "$CODE" = 404 ] && [ "$ELAPSED" -le 3 ] && echo 1 || echo 0)" "(HTTP $CODE)"

# --- 6. limity tela, neplatne case_id ---
head -c 110000000 /dev/zero > "$TMP/huge.bin"   # 104,9 MiB; limit je 100 MiB = 104 857 600 B
authed POST "$URL" -H "Transfer-Encoding: chunked" -F "files=@$TMP/huge.bin;type=application/pdf"
code_is "chunked telo nad 100 MB (bez Content-Length) -> 413" 413
authed POST "$URL" -F "files=@$TMP/huge.bin;type=application/pdf"; code_is "Content-Length nad 100 MB -> 413" 413
authed GET "$BASE_URL/v1/cases/../documents" --path-as-is; code_is "case_id '..' -> 400" 400
authed GET "$BASE_URL/v1/cases/./documents" --path-as-is;  code_is "case_id '.' -> 400" 400

# --- 7. stejny obsah v jinem case: also_in (index obsahovych hashu wonderfulkb-uw-content-hashes) ---
authed POST "$BASE_URL/v1/cases/$CASE2/documents" -F "files=@${PDFS[0]};type=application/pdf"
code_is "stejne PDF do druheho case -> 201" 201
check "bez ?include_also_in pole also_in chybi (ID cizich case se nevraci)" "$(py "'also_in' not in d['documents'][0]")"
authed POST "$BASE_URL/v1/cases/$CASE2/documents?include_also_in=true" -F "files=@${PDFS[0]};type=application/pdf"
code_is "opakovane s ?include_also_in=true -> 201" 201
check "druhy case: also_in obsahuje prvni case" "$(py "'$CASE_ID' in [x['case_id'] for x in d['documents'][0]['also_in']]")"
check "also_in neobsahuje vlastni case" "$(py "'$CASE2' not in [x['case_id'] for x in d['documents'][0]['also_in']]")"
