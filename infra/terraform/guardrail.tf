resource "aws_bedrock_guardrail" "this" {
  count = var.enable_guardrail ? 1 : 0

  name                      = local.name
  description               = "IncidentScribe: block prompt attacks and harmful content, mask personal data"
  blocked_input_messaging   = "This incident text was blocked by the safety guardrail."
  blocked_outputs_messaging = "The generated summary was blocked by the safety guardrail."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
    filters_config {
      type            = "HATE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "LOW"
      output_strength = "LOW"
    }
    tier_config {
      tier_name = "CLASSIC"
    }
  }

  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = ["EMAIL", "PHONE", "CREDIT_DEBIT_CARD_NUMBER", "AWS_ACCESS_KEY", "AWS_SECRET_KEY", "PASSWORD"]
      content {
        type   = pii_entities_config.value
        action = "ANONYMIZE"
      }
    }
  }
}

resource "aws_bedrock_guardrail_version" "this" {
  count         = var.enable_guardrail ? 1 : 0
  guardrail_arn = aws_bedrock_guardrail.this[0].guardrail_arn
  description   = "managed by terraform"

  # Publish a new version whenever the guardrail definition changes.
  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.this[count.index]]
  }
}
