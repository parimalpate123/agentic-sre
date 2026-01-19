# EventBridge Rule for CloudWatch Alarms
resource "aws_cloudwatch_event_rule" "alarm_state_change" {
  name        = "${var.project_name}-alarm-state-change"
  description = "Capture CloudWatch Alarm state changes to ALARM"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = {
    Name = "${var.project_name}-alarm-state-change"
  }
}

# EventBridge Target - Lambda Function
resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.alarm_state_change.name
  target_id = "IncidentHandlerLambda"
  arn       = aws_lambda_function.incident_handler.arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.incident_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.alarm_state_change.arn
}
