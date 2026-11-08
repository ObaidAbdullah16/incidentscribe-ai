#!/usr/bin/env bash
# End-to-end test: force the demo CloudWatch alarm into ALARM ->
# EventBridge -> Lambda -> Bedrock -> Slack (if a webhook is set). Then reset it.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need aws terraform
TF="$REPO_ROOT/infra/terraform"
tf_init "$TF" "incidentscribe-ai/terraform.tfstate"
alarm="$(tf_out "$TF" demo_alarm_name)"
[[ -n "$alarm" ]] || die "Not deployed. Run scripts/up.sh"

aws cloudwatch set-alarm-state --alarm-name "$alarm" --state-value ALARM \
  --state-reason "Threshold Crossed: checkout-api 5xx error rate 12.4% > 5% for 3 minutes (synthetic test from send-test-alarm.sh)"
log "Alarm set to ALARM. Waiting 20 seconds for EventBridge + Lambda..."
sleep 20
aws logs tail "/aws/lambda/incidentscribe" --since 2m --format short | tail -n 20 || true
aws cloudwatch set-alarm-state --alarm-name "$alarm" --state-value OK --state-reason "reset after test"
log "Alarm reset to OK. Check Slack (if configured) and the log line above for the summary + cost."
