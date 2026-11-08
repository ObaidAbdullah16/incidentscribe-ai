#!/usr/bin/env bash
# Call the public API with one of the bundled synthetic incidents.
#   bash scripts/invoke-demo.sh            # lists samples
#   bash scripts/invoke-demo.sh DEMO-28    # PII example
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need curl terraform
TF="$REPO_ROOT/infra/terraform"
tf_init "$TF" "incidentscribe-ai/terraform.tfstate"
api="$(tf_out "$TF" api_url)"
[[ -n "$api" ]] || die "Not deployed. Run scripts/up.sh"
if [[ -z "${1:-}" ]]; then
  curl -fsS "$api/samples"; echo
  exit 0
fi
curl -fsS -X POST "$api/incidents" -H 'content-type: application/json' -d "{\"sample_id\":\"$1\"}" | python3 -m json.tool
