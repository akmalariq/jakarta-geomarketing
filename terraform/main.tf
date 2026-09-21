terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  default     = "jakarta-geomarketing"
  description = "GCP project that hosts the geomarketing platform"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Single region for storage, BigQuery, and Cloud Run. Chosen because the Cloud Storage free tier applies to US regions, and co-locating storage with BigQuery keeps load jobs free."
}

variable "bucket_name" {
  type        = string
  default     = "jakarta-geomarketing-raw"
  description = "Cloud Storage bucket for the raw and prepared Overture extracts"
}

variable "dataset_id" {
  type        = string
  default     = "geomarketing"
  description = "BigQuery dataset holding the raw tables"
}

resource "google_storage_bucket" "raw" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_bigquery_dataset" "geomarketing" {
  dataset_id  = var.dataset_id
  location    = var.region
  description = "Jakarta geomarketing: Overture Maps places and H3 opportunity scores"
}

# Service account used by the ingestion job and the Dataflow pipeline.
resource "google_service_account" "pipeline" {
  account_id   = "geomarketing-pipeline"
  display_name = "Jakarta Geomarketing Pipeline"
}

resource "google_project_iam_member" "pipeline_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bigquery_data" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# Dataflow needs to read the pipeline code and write temporary files.
resource "google_project_iam_member" "pipeline_dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

output "bucket" {
  value = google_storage_bucket.raw.name
}

output "dataset" {
  value = google_bigquery_dataset.geomarketing.dataset_id
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}
