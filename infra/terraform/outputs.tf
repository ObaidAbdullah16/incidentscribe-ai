output "api_url" {
  description = "Base URL of the public demo API (GET /health, GET /samples, POST /incidents)."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "demo_alarm_name" {
  value = aws_cloudwatch_metric_alarm.demo.alarm_name
}

output "slack_param_name" {
  value = aws_ssm_parameter.slack_webhook.name
}

output "incidents_table" {
  value = aws_dynamodb_table.incidents.name
}

output "guardrail_id" {
  value = var.enable_guardrail ? aws_bedrock_guardrail.this[0].guardrail_id : ""
}
