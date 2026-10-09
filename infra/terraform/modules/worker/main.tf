# finrag-worker: dipicu SQS (batch 1, maximum_concurrency 3). Tanpa Function URL, tanpa ingress HTTP (NF-1).
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  function_name = var.name
  role          = var.role_arn
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  timeout       = var.timeout
  memory_size   = var.memory_size

  image_config {
    command = [var.handler]
  }

  environment {
    variables = var.environment
  }

  depends_on = [aws_cloudwatch_log_group.this]
}

resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn = var.queue_arn
  function_name    = aws_lambda_function.this.arn
  batch_size       = 1
  enabled          = var.enabled

  scaling_config {
    maximum_concurrency = 3
  }
}
