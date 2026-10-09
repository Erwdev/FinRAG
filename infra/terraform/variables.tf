variable "region" {
  type        = string
  default     = "us-east-1"
  description = "Satu region untuk seluruh AWS (aturan E1)."
}

variable "prefix" {
  type    = string
  default = "finrag"
}

variable "image_tag" {
  type        = string
  default     = "hello"
  description = "Tag image di ECR untuk finrag-api dan finrag-worker. Image harus sudah ada sebelum apply Lambda."
}

variable "budget_email" {
  type        = string
  description = "Alamat email untuk alert AWS Budgets."
}

variable "budget_limit_usd" {
  type    = number
  default = 10
}

variable "api_reserved_concurrency" {
  type        = number
  default     = 5
  nullable    = true
  description = "reserved_concurrent_executions finrag-api. Set null bila kuota akun baru menolaknya (bagian 1.1)."
}

variable "worker_enabled" {
  type        = bool
  default     = false
  description = "Aktifkan event source mapping SQS ke finrag-worker. Diaktifkan pada jam 18 sampai 26 (bagian 13)."
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "ssm_path" {
  type    = string
  default = "/finrag/prod/"
}

variable "ssm_parameter_names" {
  type = list(string)
  default = [
    "CLERK_JWKS_URL",
    "CLERK_ISSUER",
    "ALLOWED_ORIGINS",
    "DATABASE_URL",
    "MOTHERDUCK_TOKEN_RO",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "LLM_BASE_URL",
    "CF_AIG_TOKEN",
    "LLM_API_KEY",
    "PINECONE_API_KEY",
    "SENTRY_DSN",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "HANDOFF_WEBHOOK_URL",
  ]
  description = "Nama parameter SSM (di bawah ssm_path). Nilai diisi manual, tidak masuk state (ignore_changes)."
}
