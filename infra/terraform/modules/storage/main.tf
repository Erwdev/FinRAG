# Bucket landing, path deterministik bagian 4.2.
resource "google_storage_bucket" "landing" {
  name                        = "${var.prefix}-landing-${var.project_id}"
  project                     = var.project_id
  location                    = var.location
  uniform_bucket_level_access = true
}
