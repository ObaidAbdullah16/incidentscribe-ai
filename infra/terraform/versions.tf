terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = "incidentscribe-ai"
      ManagedBy = "terraform"
      DataClass = "synthetic"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  name       = "incidentscribe"
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  # "apac.amazon.nova-micro-v1:0" -> "amazon.nova-micro-v1:0" (the model behind a cross-region inference profile)
  base_model_id = replace(var.model_id, "/^(us|eu|apac|global|jp|au|ca|us-gov)\\./", "")
  is_profile    = local.base_model_id != var.model_id
}
