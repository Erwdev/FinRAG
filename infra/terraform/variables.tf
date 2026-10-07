variable "project_id" {
  type        = string
  description = "Proyek GCP dengan billing aktif"
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "prefix" {
  type    = string
  default = "finrag"
}

variable "worker_image" {
  type        = string
  description = "Image finrag-api, diisi setelah build pertama"
  default     = "gcr.io/PROJECT_ID/finrag-api:latest"
}
