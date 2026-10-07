output "dataset_ids" {
  value = [
    google_bigquery_dataset.raw.dataset_id,
    google_bigquery_dataset.stg.dataset_id,
    google_bigquery_dataset.mart.dataset_id,
  ]
}
