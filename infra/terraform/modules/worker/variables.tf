variable "name" {
  type = string
}

variable "image_uri" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "handler" {
  type = string
}

variable "timeout" {
  type = number
}

variable "memory_size" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "environment" {
  type = map(string)
}

variable "queue_arn" {
  type = string
}

variable "enabled" {
  type    = bool
  default = false
}
