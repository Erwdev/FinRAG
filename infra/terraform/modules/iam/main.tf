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
