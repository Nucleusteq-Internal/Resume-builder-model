variable "aws_region" {
  description = "AWS Region"
  type        = string
}

variable "tags" {
  type = map(string)
}

variable "aws_account_id" {
  type = string
}

variable "app_name" {
  type = string
}

variable "eks_cluster_name" {
  type = string
}
