# Default table expiration: Never (bawaan Terraform, tanpa expiration_ms).
resource "google_bigquery_dataset" "raw" {
  project    = var.project_id
  dataset_id = "finrag_raw"
  location   = var.location
}

resource "google_bigquery_dataset" "stg" {
  project    = var.project_id
  dataset_id = "finrag_stg"
  location   = var.location
}

resource "google_bigquery_dataset" "mart" {
  project    = var.project_id
  dataset_id = "finrag_mart"
  location   = var.location
}

resource "google_bigquery_dataset_iam_member" "mart_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.mart.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${var.app_sa_email}"
}

# Data Editor sa-flows pada ketiga dataset (bagian 3.4).
resource "google_bigquery_dataset_iam_member" "flows_raw_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.flows_sa_email}"
}

resource "google_bigquery_dataset_iam_member" "flows_stg_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.stg.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.flows_sa_email}"
}

resource "google_bigquery_dataset_iam_member" "flows_mart_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.mart.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.flows_sa_email}"
}
