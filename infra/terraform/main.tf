data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Lingkungan Lambda. Rahasia tidak ada di sini (ada di SSM, lihat bagian 11.7).
  common_env = {
    SSM_PATH       = var.ssm_path
    SQS_QUEUE_URL  = module.queue.queue_url
    LANDING_BUCKET = module.storage.bucket_name
    MD_DATABASE    = "finrag"
  }
}

module "storage" {
  source      = "./modules/storage"
  bucket_name = "${var.prefix}-landing-${local.account_id}"
}

module "queue" {
  source = "./modules/queue"
  name   = "${var.prefix}-chat-jobs"
}

module "ecr" {
  source = "./modules/ecr"
  name   = "${var.prefix}-api"
}

module "ssm" {
  source = "./modules/ssm"
  path   = var.ssm_path
  names  = var.ssm_parameter_names
}

module "iam" {
  source             = "./modules/iam"
  prefix             = var.prefix
  region             = var.region
  account_id         = local.account_id
  landing_bucket_arn = module.storage.bucket_arn
  queue_arn          = module.queue.queue_arn
  ssm_path           = var.ssm_path
}

module "api" {
  source              = "./modules/api"
  name                = "finrag-api"
  image_uri           = "${module.ecr.repository_url}:${var.image_tag}"
  role_arn            = module.iam.api_role_arn
  handler             = "app.lambda_api.handler"
  timeout             = 30
  memory_size         = 1024
  reserved_concurrency = var.api_reserved_concurrency
  log_retention_days  = var.log_retention_days
  environment         = local.common_env
}

module "worker" {
  source             = "./modules/worker"
  name               = "finrag-worker"
  image_uri          = "${module.ecr.repository_url}:${var.image_tag}"
  role_arn           = module.iam.worker_role_arn
  handler            = "app.lambda_worker.handler"
  timeout            = 120
  memory_size        = 1769
  log_retention_days = var.log_retention_days
  environment        = local.common_env
  queue_arn          = module.queue.queue_arn
  enabled            = var.worker_enabled
}

# Budget alert: peringatan di 50 dan 90 persen (bagian 3.4).
resource "aws_budgets_budget" "monthly" {
  name         = "${var.prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 90]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_email]
    }
  }
}
