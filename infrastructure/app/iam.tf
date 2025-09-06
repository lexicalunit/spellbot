# IAM Role for SpellBot Application Deployment

# Deployment role that can be assumed by CI/CD systems
resource "aws_iam_role" "spellbot_deployment" {
  name        = "spellbot-deployment-role"
  description = "IAM role for SpellBot application deployment"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          },
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:lexicalunit/spellbot:*"
        } }
      }
    ]
  })

  tags = {
    Name = "spellbot-deployment-role"
  }
}

# Data source for current AWS account ID
data "aws_caller_identity" "current" {}

# GitHub OIDC Identity Provider
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Name = "github-actions-oidc"
  }
}

# Custom policy for ECR operations
resource "aws_iam_policy" "spellbot_ecr_deployment" {
  name        = "spellbot-ecr-deployment"
  description = "Permissions for ECR image management"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:DescribeImages",
          "ecr:ListImages"
        ]
        Resource = [
          aws_ecr_repository.spellbot.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "spellbot-ecr-deployment"
  }
}

# Custom policy for ECS deployment operations
resource "aws_iam_policy" "spellbot_ecs_deployment" {
  name        = "spellbot-ecs-deployment"
  description = "Permissions for ECS task definition and service management"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DescribeTaskDefinition",
          "ecs:DeregisterTaskDefinition",
          "ecs:ListTaskDefinitions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:ListServices"
        ]
        Resource = [
          "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.main.name}/spellbot-prod",
          "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.main.name}/spellbot-stage"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
          "ecs:ListTasks"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ecs:cluster" = aws_ecs_cluster.main.arn
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:DescribeClusters"
        ]
        Resource = [
          aws_ecs_cluster.main.arn
        ]
      }
    ]
  })

  tags = {
    Name = "spellbot-ecs-deployment"
  }
}

# Custom policy for SSM parameter management
resource "aws_iam_policy" "spellbot_ssm_deployment" {
  name        = "spellbot-ssm-deployment"
  description = "Permissions for SSM parameter management"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:PutParameter",
          "ssm:DeleteParameter",
          "ssm:DescribeParameters"
        ]
        Resource = [
          "${aws_ssm_parameter.spellbot_prod_image_uri.arn}",
          "${aws_ssm_parameter.spellbot_stage_image_uri.arn}"
        ]
      }
    ]
  })

  tags = {
    Name = "spellbot-ssm-deployment"
  }
}

# Custom policy for IAM pass role (needed for ECS task execution)
resource "aws_iam_policy" "spellbot_iam_passrole" {
  name        = "spellbot-iam-passrole"
  description = "Permissions to pass ECS roles"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "spellbot-iam-passrole"
  }
}

# Attach ECR policy to deployment role
resource "aws_iam_role_policy_attachment" "spellbot_deployment_ecr" {
  role       = aws_iam_role.spellbot_deployment.name
  policy_arn = aws_iam_policy.spellbot_ecr_deployment.arn
}

# Attach ECS policy to deployment role
resource "aws_iam_role_policy_attachment" "spellbot_deployment_ecs" {
  role       = aws_iam_role.spellbot_deployment.name
  policy_arn = aws_iam_policy.spellbot_ecs_deployment.arn
}

# Attach SSM policy to deployment role
resource "aws_iam_role_policy_attachment" "spellbot_deployment_ssm" {
  role       = aws_iam_role.spellbot_deployment.name
  policy_arn = aws_iam_policy.spellbot_ssm_deployment.arn
}

# Attach IAM PassRole policy to deployment role
resource "aws_iam_role_policy_attachment" "spellbot_deployment_iam" {
  role       = aws_iam_role.spellbot_deployment.name
  policy_arn = aws_iam_policy.spellbot_iam_passrole.arn
}
