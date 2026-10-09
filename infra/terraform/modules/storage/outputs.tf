output "bucket_name" {
  value = aws_s3_bucket.landing.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.landing.arn
}
