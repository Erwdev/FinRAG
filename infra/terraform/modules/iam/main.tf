# Akun layanan sesuai bagian 3.4. Peran terikat di modul pemilik sumber daya.
resource "google_service_account" "app" {
  project      = var.project_id
  account_id   = "sa-app"
  display_name = "FinRAG API (Cloud Run)"
}

resource "google_service_account" "tasks_invoker" {
  project      = var.project_id
  account_id   = "sa-tasks-invoker"
  display_name = "Cloud Tasks invoker"
}

resource "google_service_account" "flows" {
  project      = var.project_id
  account_id   = "sa-flows"
  display_name = "Prefect flows"
}

# Peran proyek sesuai bagian 3.4.
resource "google_project_iam_member" "app_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "app_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "flows_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.flows.email}"
}

# sa-app bertindak sebagai sa-tasks-invoker saat membuat task (bagian 3.4).
resource "google_service_account_iam_member" "app_acts_as_tasks_invoker" {
  service_account_id = google_service_account.tasks_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.app.email}"
}
