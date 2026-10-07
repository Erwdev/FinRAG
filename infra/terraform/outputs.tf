output "worker_uri" {
  value = module.worker.uri
}

output "sa_app_email" {
  value = module.iam.app_sa_email
}

output "landing_bucket" {
  value = module.storage.bucket_name
}

output "tasks_queue" {
  value = module.tasks.queue_id
}
