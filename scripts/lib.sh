#!/usr/bin/env bash
# shellcheck disable=SC2034  # variables defined here are used by the scripts that source it
# Shared helpers for this repo's up/down/status scripts. Sourced, not executed.
# Settings come from the environment, or from ../_setup/config.env when this repo
# sits inside the Projects_Demos folder.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$REPO_ROOT/../_setup/config.env" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/../_setup/config.env"
fi
: "${AWS_REGION:=ap-southeast-2}"
: "${AUTO_APPROVE:=1}"          # set AUTO_APPROVE=0 to review the plan before applying
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
[[ -n "${AWS_PROFILE:-}" ]] && export AWS_PROFILE
: "${GITHUB_OWNER:=${GITHUB_REPOSITORY_OWNER:-ObaidAbdullah16}}"

log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

need() {
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "'$c' is not installed (see _setup/install-tools-wsl.sh)"
  done
}

aws_account_id() { aws sts get-caller-identity --query Account --output text; }

state_bucket() { echo "${TF_STATE_BUCKET:-tfstate-$(aws_account_id)-${AWS_REGION}}"; }

# tf_init <terraform dir> <state key>
tf_init() {
  local dir="$1" key="$2" bucket
  bucket="$(state_bucket)"
  aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1 \
    || die "State bucket $bucket not found: the AWS foundation is not set up (or you are logged in to another account). Start it first: bash _setup/projects.sh up foundation"
  terraform -chdir="$dir" init -input=false -reconfigure \
    -backend-config="bucket=${bucket}" \
    -backend-config="key=${key}" \
    -backend-config="region=${AWS_REGION}" \
    -backend-config="use_lockfile=true" \
    -backend-config="encrypt=true" >/dev/null
}

tf_apply() { # tf_apply <dir> [extra args...]
  local dir="$1"; shift
  if [[ "$AUTO_APPROVE" == "1" ]]; then
    terraform -chdir="$dir" apply -input=false -auto-approve -var "aws_region=${AWS_REGION}" "$@"
  else
    terraform -chdir="$dir" apply -input=false -var "aws_region=${AWS_REGION}" "$@"
  fi
}

tf_destroy() { # tf_destroy <dir> [extra args...]
  local dir="$1"; shift
  if [[ "$AUTO_APPROVE" == "1" ]]; then
    terraform -chdir="$dir" destroy -input=false -auto-approve -var "aws_region=${AWS_REGION}" "$@"
  else
    terraform -chdir="$dir" destroy -input=false -var "aws_region=${AWS_REGION}" "$@"
  fi
}

tf_out() { terraform -chdir="$1" output -raw "$2" 2>/dev/null || true; }

# Is anything in this Terraform state? (used by status / auto-stop)
tf_has_resources() { [[ -n "$(terraform -chdir="$1" state list 2>/dev/null | grep -v '^data\.' || true)" ]]; }

# ------------------------------------------------------------------ IncidentScribe
TF="$REPO_ROOT/infra/terraform"
SLACK_PARAM="/incidentscribe/slack-webhook-url"
API_PARAM="/incidentscribe/api-url"

gh_ready() { command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; }
in_ci() { [[ -n "${GITHUB_ACTIONS:-}" ]]; }
in_state() { terraform -chdir="$TF" state list 2>/dev/null | grep -qxF "$1"; }
ssm_value() { aws ssm get-parameter --name "$1" --query Parameter.Value --output text 2>/dev/null || true; }

# Pages allowed to call the public demo API (CORS): your portfolio on its domain and on its
# CloudFront address. Empty output = leave Terraform's default (any origin).
default_allowed_origins() {
  local list=() cf
  if [[ -n "${PORTFOLIO_DOMAIN:-}" ]]; then list+=("https://${PORTFOLIO_DOMAIN}" "https://www.${PORTFOLIO_DOMAIN}"); fi
  cf="$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='Portfolio'].DomainName | [0]" --output text 2>/dev/null || true)"
  [[ "$cf" == *.cloudfront.net ]] && list+=("https://${cf}")
  [[ ${#list[@]} -gt 0 ]] || return 0
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${list[@]}"
}

# The portfolio's demo page gets the API address when the portfolio is deployed.
# After this project starts or stops, redeploy the portfolio so the page is up to date.
refresh_portfolio() {
  if [[ "${SKIP_PORTFOLIO_REFRESH:-0}" == "1" ]]; then
    return 0
  fi
  # Only when the portfolio is deployed - a Deploy run would otherwise start a stopped portfolio again.
  local n
  n="$(aws cloudfront list-distributions --query "length(DistributionList.Items[?Comment=='Portfolio'] || \`[]\`)" \
    --output text 2>/dev/null || echo unknown)"
  if [[ "$n" == "0" ]]; then
    log "The portfolio is not deployed, so its demo page needs no refresh."
    return 0
  fi
  if in_ci; then
    log "Remember: run the portfolio Deploy workflow so its demo page uses the current API address."
  elif [[ "${AWS_ACCOUNT_TYPE:-classic}" == project && -f "$REPO_ROOT/../portfolio/scripts/up.sh" ]]; then
    # Project account: GitHub cannot deploy to AWS, so redeploy the portfolio from this laptop (1-2 minutes).
    log "Redeploying the portfolio from this laptop so its demo page uses the current API address"
    bash "$REPO_ROOT/../portfolio/scripts/up.sh" || warn "Portfolio redeploy failed - run it yourself: bash _setup/projects.sh up portfolio"
  elif gh_ready && gh repo view "${GITHUB_OWNER}/portfolio" >/dev/null 2>&1; then
    if gh workflow run deploy.yml --repo "${GITHUB_OWNER}/portfolio" >/dev/null 2>&1; then
      log "Started the portfolio Deploy workflow (2-3 minutes) so its demo page uses the current API address."
    else
      warn "Could not start the portfolio Deploy workflow - run it: GitHub > portfolio > Actions > Deploy > Run workflow"
    fi
  else
    warn "Redeploy the portfolio so its demo page uses the current API address: bash ../portfolio/scripts/up.sh"
  fi
}
