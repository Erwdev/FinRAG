# Identitas sesuai Architecture.md 3.4. Lambda memakai role (tanpa kunci statis).

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------- finrag-api-role ----------
resource "aws_iam_role" "api" {
  name               = "${var.prefix}-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "EnqueueChatJobs"
    actions   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
    resources = [var.queue_arn]
  }
  statement {
    sid       = "ReadSecretsByPath"
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${var.account_id}:parameter${var.ssm_path}*"]
  }
  statement {
    sid       = "DecryptSsmDefaultKey"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.prefix}-api-inline"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# ---------- finrag-worker-role ----------
resource "aws_iam_role" "worker" {
  name               = "${var.prefix}-worker-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "worker_logs" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid = "ConsumeChatJobs"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
    ]
    resources = [var.queue_arn]
  }
  statement {
    sid       = "ReadSecretsByPath"
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${var.account_id}:parameter${var.ssm_path}*"]
  }
  statement {
    sid       = "DecryptSsmDefaultKey"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.prefix}-worker-inline"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

# ---------- finrag-prefect-writer (kunci dibuat manual, bukan di state) ----------
resource "aws_iam_user" "prefect_writer" {
  name = "${var.prefix}-prefect-writer"
}

data "aws_iam_policy_document" "prefect_writer" {
  statement {
    sid       = "WriteDltLanding"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${var.landing_bucket_arn}/dlt/*"]
  }
  statement {
    sid       = "ListDltLanding"
    actions   = ["s3:ListBucket"]
    resources = [var.landing_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["dlt/*"]
    }
  }
}

resource "aws_iam_user_policy" "prefect_writer" {
  name   = "${var.prefix}-prefect-writer-inline"
  user   = aws_iam_user.prefect_writer.name
  policy = data.aws_iam_policy_document.prefect_writer.json
}

# ---------- finrag-md-reader (MotherDuck membaca S3, baca-saja) ----------
resource "aws_iam_user" "md_reader" {
  name = "${var.prefix}-md-reader"
}

data "aws_iam_policy_document" "md_reader" {
  statement {
    sid       = "ReadLanding"
    actions   = ["s3:GetObject"]
    resources = ["${var.landing_bucket_arn}/*"]
  }
  statement {
    sid       = "ListLanding"
    actions   = ["s3:ListBucket"]
    resources = [var.landing_bucket_arn]
  }
}

resource "aws_iam_user_policy" "md_reader" {
  name   = "${var.prefix}-md-reader-inline"
  user   = aws_iam_user.md_reader.name
  policy = data.aws_iam_policy_document.md_reader.json
}
