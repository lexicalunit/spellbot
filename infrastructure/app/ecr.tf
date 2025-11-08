# ECR repository for SpellBot application
resource "aws_ecr_repository" "spellbot" {
  name                 = "spellbot-app"
  image_tag_mutability = "MUTABLE"

  tags = {
    Name = "spellbot-ecr"
  }
}

# ECR lifecycle policy to manage image retention
resource "aws_ecr_lifecycle_policy" "spellbot" {
  repository = aws_ecr_repository.spellbot.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Always retain prod images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["prod"]
          countType      = "imageCountMoreThan"
          countNumber    = 9999
        }
        action = {
          type = "retain"
        }
      },
      {
        rulePriority = 2
        description  = "Always retain stage images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["stage"]
          countType      = "imageCountMoreThan"
          countNumber    = 9999
        }
        action = {
          type = "retain"
        }
      },
      {
        rulePriority = 3
        description  = "Keep last 50 tagged images (git SHAs)"
        selection = {
          tagStatus      = "tagged"
          countType      = "imageCountMoreThan"
          countNumber    = 50
          tagPatternList = ["*"]
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 4
        description  = "Delete untagged images older than 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
