#!/usr/bin/env bash
# Store a Slack incoming-webhook URL as an SSM SecureString (never in Git or Terraform state).
#   bash scripts/set-slack-webhook.sh https://hooks.slack.com/services/T000/B000/XXXX
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
need aws
url="${1:-}"
[[ "$url" == https://hooks.slack.com/services/* ]] || die "Usage: $0 https://hooks.slack.com/services/..."
aws ssm put-parameter --name /incidentscribe/slack-webhook-url --type SecureString --overwrite --value "$url" >/dev/null
log "Saved. The function picks it up within 5 minutes (cached)."
