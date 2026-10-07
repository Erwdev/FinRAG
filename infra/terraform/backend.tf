# State Terraform disimpan di bucket Cloudflare R2.
# Bucket R2 dibuat dan seluruh isian di bawah dikonfigurasi nanti.
# Setelah diisi, jalankan: terraform init -migrate-state
#
# terraform {
#   backend "s3" {
#     bucket                      = "finrag-terraform-state"
#     key                         = "finrag/terraform.tfstate"
#     region                      = "auto"
#     endpoints                   = { s3 = "https://<ACCOUNT_ID>.r2.cloudflarestorage.com" }
#     skip_credentials_validation = true
#     skip_requesting_account_id  = true
#     skip_metadata_api_check     = true
#     use_path_style              = true
#   }
# }
