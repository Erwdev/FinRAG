variable "project_id" {
  type = string
}

variable "location" {
  type = string
}

variable "prefix" {
  type = string
}

variable "flows_sa_email" {
  type        = string
  description = "Email sa-flows untuk storageObjectAdmin pada bucket landing"
}
