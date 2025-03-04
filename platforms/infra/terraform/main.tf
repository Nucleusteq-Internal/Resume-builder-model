provider "kubernetes" {
  config_path = "~/.kube/config"
}

data "terraform_remote_state" "portal_infra" {
  backend = "s3"
  config = {
    bucket = "terraform-remote-${var.tags.project}-${var.tags.environment}"
    key    = "${var.tags.environment}/terraform.tfstate"
    region = "${var.aws_region}"
  }
}

locals {
  eks_oidc_issuer               = trimprefix(data.terraform_remote_state.portal_infra.outputs.identity-oidc-issuer, "https://")
  k8s_service_account_namespace = "plasma-namespace"
  k8s_service_account_name      = "${var.app_name}-service-account"
}

# ECR repository for all plamsa services as well as frontend
resource "aws_ecr_repository" "app_repo" {
  name                 = "resume-builder-model-repo"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "resume_builder_model_ecr_lifecycle_policy" {
  repository = aws_ecr_repository.app_repo.name
  policy     = <<POLICY
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep only 5 most recent images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 5
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
POLICY
}

# Create IAM policy allowing the service account to assume the IAM role
data "aws_iam_policy_document" "pod_role_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_issuer}:sub"
      values = [
        "system:serviceaccount:${local.k8s_service_account_namespace}:${local.k8s_service_account_name}",
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    principals {
      type = "Federated"
      identifiers = [
        "arn:aws:iam::${var.aws_account_id}:oidc-provider/${local.eks_oidc_issuer}"
      ]
    }
  }

}

data "aws_iam_policy_document" "pod_policy_document" {
  statement {
    effect = "Allow"
    actions = [
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
      "logs:DescribeLogGroups",
      "logs:CreateLogStream",
      "logs:CreateLogGroup"
    ]
    resources = [
      "arn:aws:logs:*:*:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:resume_builder_user_${var.tags.environment}_password*",
    ]
  }
}

# Create the IAM role that will be assumed by the service account
resource "aws_iam_role" "pod_role" {
  name               = "portal-${var.tags.environment}-${var.app_name}-pod-role"
  assume_role_policy = data.aws_iam_policy_document.pod_role_policy.json
  tags               = var.tags
}


resource "aws_iam_policy" "pod_policy" {
  name   = "${var.app_name}-${var.tags.environment}-pod-policy"
  policy = data.aws_iam_policy_document.pod_policy_document.json
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "pod_policy_attachment" {
  role       = aws_iam_role.pod_role.name
  policy_arn = aws_iam_policy.pod_policy.arn
}
