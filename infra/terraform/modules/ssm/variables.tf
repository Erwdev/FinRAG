variable "path" {
  type        = string
  description = "Awalan parameter, contoh /finrag/prod/"
}

variable "names" {
  type        = list(string)
  description = "Nama parameter di bawah path"
}
