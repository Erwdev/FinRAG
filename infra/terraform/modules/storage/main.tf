# Bucket landing, path deterministik bagian 4.2.
resource "google_storage_bucket" "landing" {
  name                        = "${var.prefix}-landing-${var.project_id}"
  project                     = var.project_id
  location                    = var.location
  uniform_bucket_level_access = true
}

# Object Admin sa-flows pada bucket landing (bagian 3.4).
resource "google_storage_bucket_iam_member" "flows_object_admin" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.flows_sa_email}"
}
