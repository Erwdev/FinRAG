output "api_role_arn" {
  value = aws_iam_role.api.arn
}

output "worker_role_arn" {
  value = aws_iam_role.worker.arn
}

output "prefect_writer_user_name" {
  value = aws_iam_user.prefect_writer.name
}

output "md_reader_user_name" {
  value = aws_iam_user.md_reader.name
}
