# finrag-api: Lambda dari image ECR, Function URL publik (auth NONE, bagian 3.1).
# CORS ditangani FastAPI, bukan Lambda.
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

  # Null = tidak dipasang (kuota akun baru bisa menolak).
  reserved_concurrent_executions = var.reserved_concurrency

  image_config {
    command = [var.handler]
  }

  environment {
    variables = var.environment
  }

  depends_on = [aws_cloudwatch_log_group.this]
}

resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE"
}

# Izin publik untuk Function URL. lambda:InvokeFunction ikut diberikan sebagai pengaman,
# karena kewajibannya belum diverifikasi (Architecture.md 1.1). Verifikasi di jam 0 sampai 2.
resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke_function" {
  statement_id               = "AllowPublicInvokeFunction"
  action                     = "lambda:InvokeFunction"
  function_name              = aws_lambda_function.this.function_name
  principal                  = "*"
  invoked_via_function_url   = true
  function_url_auth_type     = "NONE"
}
