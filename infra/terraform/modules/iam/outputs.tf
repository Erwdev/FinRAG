output "app_sa_email" {
  value = google_service_account.app.email
}

output "tasks_invoker_sa_email" {
  value = google_service_account.tasks_invoker.email
}

output "flows_sa_email" {
  value = google_service_account.flows.email
}
