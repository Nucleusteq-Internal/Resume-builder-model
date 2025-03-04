locals {
  vars = read_terragrunt_config("params.hcl")
  account_name = local.vars.locals.account_name
  account_id   = local.vars.locals.aws_account_id
  aws_region   = local.vars.locals.aws_region
  environment  = local.vars.locals.tags.environment
  project      = local.vars.locals.tags.project
  app_name     = local.vars.locals.app_name
}

# Generate an AWS provider block
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
    provider "aws" {
      region = "${local.aws_region}"
      # Only these AWS Account IDs may be operated on by this template
      allowed_account_ids = ["${local.account_id}"]
    }
  EOF
}

# Configure Terragrunt to automatically store tfstate files in an S3 bucket
remote_state {
  backend = "s3"
  config = {
    encrypt        = true
    bucket         = "terraform-remote-${local.project}-${local.environment}"
    key            = "${path_relative_to_include()}/${local.app_name}/terraform.tfstate"
    region         = local.aws_region
    dynamodb_table = "terraform-locks-${local.app_name}"
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

inputs = local.vars.locals
