module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id
}

module "worker" {
  source          = "./modules/worker"
  project_id      = var.project_id
  region          = var.region
  service_account = module.iam.app_sa_email
  image           = var.worker_image
}

module "bigquery" {
  source        = "./modules/bigquery"
  project_id    = var.project_id
  location      = var.region
  app_sa_email  = module.iam.app_sa_email
  flows_sa_email = module.iam.flows_sa_email
}

module "storage" {
  source        = "./modules/storage"
  project_id    = var.project_id
  location      = var.region
  prefix        = var.prefix
  flows_sa_email = module.iam.flows_sa_email
}

module "tasks" {
  source     = "./modules/tasks"
  project_id = var.project_id
  location   = var.region
}
