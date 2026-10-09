# Output yang dibutuhkan langkah berikutnya (lihat README: "Setup checklist").

output "aws_account_id" {
  value = local.account_id
}

output "region" {
  value = var.region
}

# URL publik finrag-api. Isi NEXT_PUBLIC_API_URL dengan nilai ini.
output "api_function_url" {
  value = module.api.function_url
}

output "api_function_name" {
  value = module.api.function_name
}

output "worker_function_name" {
  value = module.worker.function_name
}

output "ecr_repository_url" {
  description = "Tujuan push image: docker buildx ... --push ECR_URL:TAG"
  value       = module.ecr.repository_url
}

output "sqs_queue_url" {
  value = module.queue.queue_url
}

output "sqs_queue_arn" {
  value = module.queue.queue_arn
}

output "sqs_dlq_url" {
  value = module.queue.dlq_url
}

output "landing_bucket_name" {
  description = "LANDING_BUCKET untuk flow dan secret MotherDuck"
  value       = module.storage.bucket_name
}

output "landing_bucket_arn" {
  value = module.storage.bucket_arn
}

output "ssm_path" {
  description = "Awalan parameter SSM. Isi dengan: aws ssm put-parameter --name ${var.ssm_path}NAMA ..."
  value       = var.ssm_path
}

output "api_role_arn" {
  value = module.iam.api_role_arn
}

output "worker_role_arn" {
  value = module.iam.worker_role_arn
}

output "prefect_writer_user_name" {
  description = "Buat kunci akses manual: aws iam create-access-key --user-name <ini>"
  value       = module.iam.prefect_writer_user_name
}

output "md_reader_user_name" {
  description = "Buat kunci akses manual: aws iam create-access-key --user-name <ini>"
  value       = module.iam.md_reader_user_name
}
