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
        description  = "Keep last 20 tagged images (git SHAs)"
        selection = {
          tagStatus      = "tagged"
          countType      = "imageCountMoreThan"
          countNumber    = 20
          tagPatternList = ["*"]

        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
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
