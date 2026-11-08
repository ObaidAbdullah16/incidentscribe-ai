resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 14
}

# Every IAM role here carries the aws-foundation permissions boundary (variables.tf).
locals {
  permissions_boundary = var.permissions_boundary_name == "" ? null : "arn:${local.partition}:iam::${local.account_id}:policy/${var.permissions_boundary_name}"
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name                 = "${local.name}-lambda"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  permissions_boundary = local.permissions_boundary
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  statement {
    sid       = "Tables"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:PutItem"]
    resources = [aws_dynamodb_table.budget.arn, aws_dynamodb_table.incidents.arn]
  }

  statement {
    sid       = "SlackWebhook"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.slack_webhook.arn]
  }

  statement {
    sid     = "InvokeModel"
    actions = ["bedrock:InvokeModel"]
    resources = concat(
      ["arn:${local.partition}:bedrock:*::foundation-model/${local.base_model_id}"],
      local.is_profile ? ["arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${var.model_id}"] : []
    )
  }

  dynamic "statement" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      sid       = "ApplyGuardrail"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [aws_bedrock_guardrail.this[0].guardrail_arn]
    }
  }

  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "this" {
  function_name    = local.name
  description      = "Alert -> redacted, runbook-grounded, cost-capped incident summary"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "incidentscribe.handler.lambda_handler"
  filename         = "${path.module}/../../dist/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../dist/lambda.zip")
  memory_size      = 256
  timeout          = 30

  reserved_concurrent_executions = var.reserved_concurrency

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      MODEL_ID          = var.model_id
      GUARDRAIL_ID      = var.enable_guardrail ? aws_bedrock_guardrail.this[0].guardrail_id : ""
      GUARDRAIL_VERSION = var.enable_guardrail ? aws_bedrock_guardrail_version.this[0].version : ""
      BUDGET_TABLE      = aws_dynamodb_table.budget.name
      INCIDENTS_TABLE   = aws_dynamodb_table.incidents.name
      SLACK_PARAM       = aws_ssm_parameter.slack_webhook.name
      DAILY_CAP_USD     = tostring(var.daily_cap_usd)
      MONTHLY_CAP_USD   = tostring(var.monthly_cap_usd)
      ALLOW_CUSTOM_TEXT = var.allow_custom_text ? "true" : "false"
      MAX_TOKENS        = "500"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}
