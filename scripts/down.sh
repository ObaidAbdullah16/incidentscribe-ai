#!/usr/bin/env bash
# Remove IncidentScribe from AWS.
#
#   bash scripts/down.sh          # removes everything; keeps only your Slack webhook in SSM
#                                 # (free) so the next 'up' sends to Slack again without setup
#   bash scripts/down.sh --all    # also deletes the saved Slack webhook and leftover log groups
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need aws terraform python3

ALL=0
for a in "$@"; do
  case "$a" in
    --all) ALL=1 ;;
    *) die "unknown option: $a (use --all or nothing)" ;;
  esac
done

[[ -f "$REPO_ROOT/dist/lambda.zip" ]] || bash "$REPO_ROOT/scripts/build.sh"
tf_init "$TF" "incidentscribe-ai/terraform.tfstate"

if [[ "$ALL" != 1 ]] && in_state aws_ssm_parameter.slack_webhook && [[ "$(ssm_value "$SLACK_PARAM")" != "none" ]]; then
  terraform -chdir="$TF" state rm aws_ssm_parameter.slack_webhook >/dev/null
  log "Keeping your Slack webhook in SSM ($SLACK_PARAM, free) for the next 'up'"
fi

if tf_has_resources "$TF"; then
  tf_destroy "$TF"
  refresh_portfolio
else
  log "Already down"
fi

if [[ "$ALL" == 1 ]]; then
  aws ssm delete-parameter --name "$SLACK_PARAM" >/dev/null 2>&1 && log "Deleted the saved Slack webhook" || true
  for lg in $(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/incidentscribe \
      --query 'logGroups[].logGroupName' --output text 2>/dev/null); do
    aws logs delete-log-group --log-group-name "$lg" && log "Deleted log group $lg"
  done
fi
log "Down. Nothing from IncidentScribe is left running."
