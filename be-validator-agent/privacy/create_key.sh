#!/usr/bin/env bash
# Vytvoří KMS klíč pro šifrování výřezů podpisů: alias/wonderfulkb-signatures, tag project=wonderfulkb.
#
# STAV: klíč už existuje (vytvořila ho nadřazená session se souhlasem uživatele 19. 10. 2026, id
# <KMS_KEY_ID>). Skript je jen dokumentace, nespouštět znovu.
#
# NESPOUŠTĚT bez souhlasu uživatele. Klíč ve sdíleném účtu stojí peníze (zhruba 1 USD měsíčně + poplatky za
# požadavky, ceník ověřit) a nejde ihned smazat (nejdřív 7 až 30 dní čekání). Výchozí běh je suchý (jen vypíše
# příkazy). Skutečné vytvoření: CONFIRM=yes ./create_key.sh
#
# Proměnné: AWS_PROFILE (výchozí hackathon), AWS_REGION (výchozí eu-central-1), ALIAS, CONFIRM.
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-hackathon}"
export AWS_REGION="${AWS_REGION:-eu-central-1}"
ALIAS="${ALIAS:-alias/wonderfulkb-signatures}"
DESC="wonderfulkb: envelope sifrovani vyrezu podpisu (GenerateDataKey/Decrypt)"

run() {
  if [[ "${CONFIRM:-}" == "yes" ]]; then "$@"; else printf '[suchy beh]'; printf ' %q' "$@"; printf '\n'; fi
}

if [[ "${CONFIRM:-}" == "yes" ]]; then
  existing=$(aws kms describe-key --key-id "$ALIAS" --query KeyMetadata.KeyId --output text 2>/dev/null || true)
  if [[ -n "$existing" && "$existing" != "None" ]]; then
    echo "Alias $ALIAS uz existuje (klic $existing), nic se nevytvari."
    exit 0
  fi
else
  echo "Suchy beh: nic se nevytvari. Pro vytvoreni spust: CONFIRM=yes $0"
fi

if [[ "${CONFIRM:-}" == "yes" ]]; then
  KEY_ID=$(aws kms create-key \
    --description "$DESC" \
    --key-usage ENCRYPT_DECRYPT --key-spec SYMMETRIC_DEFAULT \
    --tags TagKey=project,TagValue=wonderfulkb \
    --query KeyMetadata.KeyId --output text)
else
  run aws kms create-key --description "$DESC" --key-usage ENCRYPT_DECRYPT --key-spec SYMMETRIC_DEFAULT \
    --tags TagKey=project,TagValue=wonderfulkb --query KeyMetadata.KeyId --output text
  KEY_ID="<KEY_ID>"
fi

run aws kms create-alias --alias-name "$ALIAS" --target-key-id "$KEY_ID"
run aws kms enable-key-rotation --key-id "$KEY_ID"

[[ "${CONFIRM:-}" == "yes" ]] || exit 0
echo "Hotovo. Politika klice zustala vychozi (pristup pres IAM uctu). Zprisneni (Decrypt jen pro roli API Lambdy,"
echo "GenerateDataKey jen pro roli pipeline) viz be-validator-agent/docs/validator-agent-privacy.md, cast 7."
echo "Nastav PRIVACY_KMS_KEY_ID=$ALIAS v prostredi Lambdy a pipeline."
