resource "aws_ecr_repository" "klaviyo_handler" {
  name                 = "klaviyo_handler"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  depends_on = [
    data.aws_ecr_authorization_token.token
  ]
}

resource "aws_ecr_lifecycle_policy" "klaviyo_handler_policy" {
  repository = aws_ecr_repository.klaviyo_handler.name

  policy = <<EOF
{
    "rules": [
        {
            "rulePriority": 1,
            "description": "Expire images older than 14 days",
            "selection": {
                "tagStatus": "untagged",
                "countType": "sinceImagePushed",
                "countUnit": "days",
                "countNumber": 14
            },
            "action": {
                "type": "expire"
            }
        }
    ]
}
EOF
}

resource "aws_lambda_function" "klaviyo_handler" {
  function_name = "klaviyo-handler"
  image_uri     = "${local.account_id}.dkr.ecr.${local.region}.amazonaws.com/${aws_ecr_repository.klaviyo_handler.name}:latest"
  package_type  = "Image"
  role          = aws_iam_role.klaviyo_handler_lambda_role.arn
  timeout       = 30

  environment {
    variables = {
      KLAVIYO_TOKEN    = ""
      BLVD_BUSINESS_ID = ""
      BLVD_SECRET_KEY  = ""
      BLVD_API_KEY     = ""
    }
  }

  depends_on = [
    aws_ecr_repository.klaviyo_handler
  ]
}

resource "aws_cloudwatch_log_group" "klaviyo_handler_lambda_log_group" {
  name              = "/aws/lambda/klaviyo-handler"
  retention_in_days = 7
  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_iam_policy" "lambda_cloudwatch" {
  name        = "klaviyo-handler-lambda-cw-permissions"
  description = "Contains CW put permission for klaviyo-handler lambda"
  policy      = data.aws_iam_policy_document.lambda_cloudwatch.json
}

resource "aws_iam_role" "klaviyo_handler_lambda_role" {
  name               = "klaviyo-handler-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_cloudwatch" {
  role       = aws_iam_role.klaviyo_handler_lambda_role.name
  policy_arn = aws_iam_policy.lambda_cloudwatch.arn
}

resource "aws_api_gateway_rest_api" "api" {
  name        = "APIGatewayServerless"
  description = "APIGateway for lambda executions"
}

resource "aws_api_gateway_resource" "customer" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "customer"
}

resource "aws_api_gateway_method" "customer" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.customer.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "klaviyo_handler" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_method.customer.resource_id
  http_method = aws_api_gateway_method.customer.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.klaviyo_handler.invoke_arn
}

resource "aws_lambda_permission" "klaviyo_handler_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.klaviyo_handler.function_name
  principal     = "apigateway.amazonaws.com"

  # The /*/* portion grants access from any method on any resource
  # within the API Gateway "REST API".
  source_arn = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_integration.klaviyo_handler,
  ]

  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = "main"
}

# * API Gateway API deployment
