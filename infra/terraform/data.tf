resource "aws_dynamodb_table" "budget" {
  name         = "${local.name}-budget"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

resource "aws_dynamodb_table" "incidents" {
  name         = "${local.name}-incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

# The webhook URL is a secret: Terraform creates a placeholder and never reads the real value back.
# Set it with: bash scripts/set-slack-webhook.sh https://hooks.slack.com/services/...
resource "aws_ssm_parameter" "slack_webhook" {
  name  = "/${local.name}/slack-webhook-url"
  type  = "SecureString"
  value = "none"

  lifecycle {
    ignore_changes = [value]
  }
}

# Public, non-secret: lets the portfolio site find the demo API at deploy time.
resource "aws_ssm_parameter" "api_url" {
  name  = "/${local.name}/api-url"
  type  = "String"
  value = aws_apigatewayv2_api.this.api_endpoint
}
