variable "prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "landing_bucket_arn" {
  type = string
}

variable "queue_arn" {
  type = string
}

variable "ssm_path" {
  type        = string
  description = "Contoh /finrag/prod/"
}
