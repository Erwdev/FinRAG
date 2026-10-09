# State Terraform disimpan di S3 (use_lockfile = native locking, tanpa DynamoDB).
# Bucket state dibuat manual sekali (Architecture.md 3.3):
#   aws s3api create-bucket --bucket finrag-tfstate-ACCOUNT_ID --region us-east-1
#   aws s3api put-bucket-versioning --bucket finrag-tfstate-ACCOUNT_ID --versioning-configuration Status=Enabled
# Lalu aktifkan blok di bawah, ganti ACCOUNT_ID, dan jalankan: terraform init -migrate-state
#
# terraform {
#   backend "s3" {
#     bucket       = "finrag-tfstate-ACCOUNT_ID"
#     key          = "finrag/terraform.tfstate"
#     region       = "us-east-1"
#     encrypt      = true
#     use_lockfile = true
#   }
# }
