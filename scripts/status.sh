#!/usr/bin/env bash
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need aws terraform
TF="$REPO_ROOT/infra/terraform"
tf_init "$TF" "incidentscribe-ai/terraform.tfstate"
if ! tf_has_resources "$TF"; then
  echo "incidentscribe-ai: DOWN"
  exit 0
fi
api="$(tf_out "$TF" api_url)"
echo "incidentscribe-ai: UP  (idle cost ~\$0; AI spend capped)"
echo "  API:    $api"
echo "  health: $(curl -fsS "$api/health" 2>/dev/null || echo unreachable)"
month="$(date -u +%Y-%m)"
aws dynamodb get-item --table-name incidentscribe-budget --key "{\"pk\":{\"S\":\"month#${month}\"}}" \
  --query 'Item.{spend_micro_usd:spend_micro_usd.N,calls:calls.N}' --output table 2>/dev/null || true
