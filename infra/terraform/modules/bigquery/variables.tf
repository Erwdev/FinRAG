variable "project_id" {
  type = string
}

variable "location" {
  type = string
}

variable "app_sa_email" {
  type        = string
  description = "Email sa-app untuk akses dataViewer pada finrag_mart"
}

variable "flows_sa_email" {
  type        = string
  description = "Email sa-flows untuk akses dataEditor pada finrag_raw, finrag_stg, finrag_mart"
}
