# Every CloudWatch alarm whose name starts with one of var.alarm_prefixes and goes to ALARM
# is sent to the function (EventBridge delivers alarm state changes for free).
resource "aws_cloudwatch_event_rule" "alarms" {
  name        = "${local.name}-alarms"
  description = "CloudWatch alarms -> IncidentScribe"
  event_pattern = jsonencode({
    source        = ["aws.cloudwatch"]
    "detail-type" = ["CloudWatch Alarm State Change"]
    detail = {
      state     = { value = ["ALARM"] }
      alarmName = [for p in var.alarm_prefixes : { prefix = p }]
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule = aws_cloudwatch_event_rule.alarms.name
  arn  = aws_lambda_function.this.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.alarms.arn
}

# A demo alarm on a custom metric that never receives data: it stays OK until
# scripts/send-test-alarm.sh forces it into ALARM (end-to-end test, no real outage needed).
resource "aws_cloudwatch_metric_alarm" "demo" {
  alarm_name          = "${local.name}-demo-checkout-errors"
  alarm_description   = "DEMO: checkout API 5xx error rate above 5% (synthetic, triggered by send-test-alarm.sh)"
  namespace           = "IncidentScribe/Demo"
  metric_name         = "CheckoutErrorRate"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    Service = "checkout-api"
  }
}
