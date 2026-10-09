output "parameter_arns" {
  value = []
}

output "parameter_names" {
  value = [for name in var.names : "${var.path}${name}"]
}
