terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.13.1"
    }
  }
}

provider "aws" {
  profile = "silvermirror"
  region  = "us-east-1"
}