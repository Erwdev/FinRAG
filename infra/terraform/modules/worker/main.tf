# Satu layanan finrag-api. Worker = route /internal/jobs/{job_id}/run pada layanan ini.
resource "google_cloud_run_v2_service" "api" {
  name     = "finrag-api"
  location = var.region
  project  = var.project_id

  template {
    service_account = var.service_account

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }
  }

  ingress = "INGRESS_TRAFFIC_ALL"
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
