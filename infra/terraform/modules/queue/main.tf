# SQS chat-jobs + DLQ (bagian 3.2). Standard, bukan FIFO. Worker idempoten lewat klaim atomik.
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 86400
}

resource "aws_sqs_queue" "main" {
  name                       = var.name
  visibility_timeout_seconds = 720 # 6 x timeout fungsi worker (120 detik)
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 2
  })
}
