# Queue chat-jobs (bagian 3.3).
resource "google_cloud_tasks_queue" "chat_jobs" {
  name     = "chat-jobs"
  project  = var.project_id
  location = var.location

  rate_limits {
    max_dispatches_per_second = 2
    max_concurrent_dispatches = 3
  }

  retry_config {
    max_attempts = 2
  }
}
