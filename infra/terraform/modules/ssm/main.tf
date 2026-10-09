# Parameter SecureString untuk Lambda. Nilai asli diisi manual lewat aws ssm put-parameter.
# ignore_changes = value: Terraform tidak pernah menimpa nilai yang sudah diisi.
resource "aws_ssm_parameter" "secret" {
  for_each = toset(var.names)

  name      = "${var.path}${each.value}"
  type      = "SecureString"
  value     = "CHANGE_ME"
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}
