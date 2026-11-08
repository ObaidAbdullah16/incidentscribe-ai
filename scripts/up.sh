#!/usr/bin/env bash
# Deploy (or update) IncidentScribe. Idle cost is ~$0: Lambda, HTTP API and DynamoDB are
# pay-per-request; Bedrock spend is capped in code at $0.15/day and $4.50/month.
#
#   bash scripts/up.sh                                   # CORS: your portfolio (domain + CloudFront address)
#   ALLOWED_ORIGINS='["https://example.com"]' bash scripts/up.sh
#   MODEL_ID=apac.amazon.nova-micro-v1:0 bash scripts/up.sh
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need aws terraform python3 curl

bash "$REPO_ROOT/scripts/build.sh"
tf_init "$TF" "incidentscribe-ai/terraform.tfstate"
old_api="$(ssm_value "$API_PARAM")"

extra=()
origins="${ALLOWED_ORIGINS:-$(default_allowed_origins)}"
if [[ -n "$origins" ]]; then
  extra+=(-var "allowed_origins=${origins}")
  log "Demo API accepts browser calls from: $origins"
fi
# Nova Micro through the cross-Region profile of your Region's geography (Asia-Pacific is the default).
if [[ -z "${MODEL_ID:-}" ]]; then
  case "$AWS_REGION" in
    us-*) MODEL_ID="us.amazon.nova-micro-v1:0" ;;
    eu-*) MODEL_ID="eu.amazon.nova-micro-v1:0" ;;
  esac
fi
[[ -n "${MODEL_ID:-}" ]] && extra+=(-var "model_id=${MODEL_ID}")

# A Slack webhook kept by the last 'down' (it is a secret you set once): adopt it again.
if [[ -n "$(ssm_value "$SLACK_PARAM")" ]] && ! in_state aws_ssm_parameter.slack_webhook; then
  log "Re-using the Slack webhook saved in SSM ($SLACK_PARAM)"
  terraform -chdir="$TF" import -input=false -var "aws_region=${AWS_REGION}" "${extra[@]}" \
    aws_ssm_parameter.slack_webhook "$SLACK_PARAM" >/dev/null \
    || warn "could not adopt the saved webhook - set it again: bash scripts/set-slack-webhook.sh <url>"
fi

tf_apply "$TF" "${extra[@]}"

api="$(tf_out "$TF" api_url)"
log "API: ${api}"
health=""
for _ in $(seq 1 12); do
  health="$(curl -fsS -m 5 "${api}/health" 2>/dev/null || true)"
  [[ -n "$health" ]] && break
  sleep 5
done
log "Health: ${health:-not ready yet - try again in a minute: bash scripts/status.sh}"
[[ "$(ssm_value "$SLACK_PARAM")" == "none" ]] && log "Optional: send summaries to Slack: bash scripts/set-slack-webhook.sh https://hooks.slack.com/services/..."

[[ "$api" != "$old_api" ]] && refresh_portfolio
log "Try it:  bash scripts/invoke-demo.sh DEMO-28      End-to-end alarm test:  bash scripts/send-test-alarm.sh"
log "Stop it: bash scripts/down.sh   (idle cost is ~\$0, so you can also leave it running)"
