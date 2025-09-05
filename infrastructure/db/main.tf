
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.21.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
  backend "s3" {
    bucket = "spellbot-terraform-state"
    key    = "spellbot-db"
    region = "us-east-2"
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Terraform   = "true"
      Environment = "shared"
      App         = "spellbot"
    }
  }
}



# PostgreSQL provider configuration
provider "postgresql" {
  host      = var.db_host
  port      = var.db_port
  database  = "postgres"
  username  = var.root_db_user
  password  = var.root_db_password
  sslmode   = "require"
  superuser = false
}

# Generate random passwords for spellbot users
resource "random_password" "stage_spellbot_password" {
  length  = 32
  special = false
}

resource "random_password" "prod_spellbot_password" {
  length  = 32
  special = false
}

# Create databases
resource "postgresql_database" "stage_db" {
  name  = "spellbot_stage"
  owner = var.root_db_user
}

resource "postgresql_database" "prod_db" {
  name  = "spellbot_prod"
  owner = var.root_db_user
}

# Create stage spellbot user
resource "postgresql_role" "stage_spellbot_user" {
  name     = "spellbot_stage_user"
  login    = true
  password = random_password.stage_spellbot_password.result
}

# Create prod spellbot user
resource "postgresql_role" "prod_spellbot_user" {
  name     = "spellbot_prod_user"
  login    = true
  password = random_password.prod_spellbot_password.result
}

# Grant privileges on stage database
resource "postgresql_grant" "stage_db_privileges" {
  database    = postgresql_database.stage_db.name
  role        = postgresql_role.stage_spellbot_user.name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "stage_table_privileges" {
  database    = postgresql_database.stage_db.name
  role        = postgresql_role.stage_spellbot_user.name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_grant" "stage_sequence_privileges" {
  database    = postgresql_database.stage_db.name
  role        = postgresql_role.stage_spellbot_user.name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]
}

# Grant privileges on prod database
resource "postgresql_grant" "prod_db_privileges" {
  database    = postgresql_database.prod_db.name
  role        = postgresql_role.prod_spellbot_user.name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "prod_table_privileges" {
  database    = postgresql_database.prod_db.name
  role        = postgresql_role.prod_spellbot_user.name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_grant" "prod_sequence_privileges" {
  database    = postgresql_database.prod_db.name
  role        = postgresql_role.prod_spellbot_user.name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]
}

# Store passwords in AWS Secrets Manager
resource "aws_secretsmanager_secret" "stage_spellbot_password" {
  name        = "spellbot/stage/db-details"
  description = "Password for stage spellbot database user"

  tags = {
    Environment = "stage"
    Component   = "database"
  }
}

resource "aws_secretsmanager_secret_version" "stage_spellbot_password" {
  secret_id = aws_secretsmanager_secret.stage_spellbot_password.id
  secret_string = jsonencode({
    username = postgresql_role.stage_spellbot_user.name
    password = random_password.stage_spellbot_password.result
    database = postgresql_database.stage_db.name
    host     = var.db_host
    port     = var.db_port
    DB_URL   = "postgresql://${postgresql_role.stage_spellbot_user.name}:${random_password.stage_spellbot_password.result}@${var.db_host}:${var.db_port}/${postgresql_database.stage_db.name}"
  })
}

resource "aws_secretsmanager_secret" "prod_spellbot_password" {
  name        = "spellbot/prod/db-details"
  description = "Password for prod spellbot database user"

  tags = {
    Environment = "prod"
    Component   = "database"
  }
}

resource "aws_secretsmanager_secret_version" "prod_spellbot_password" {
  secret_id = aws_secretsmanager_secret.prod_spellbot_password.id
  secret_string = jsonencode({
    username = postgresql_role.prod_spellbot_user.name
    password = random_password.prod_spellbot_password.result
    database = postgresql_database.prod_db.name
    host     = var.db_host
    port     = var.db_port
    DB_URL   = "postgresql://${postgresql_role.prod_spellbot_user.name}:${random_password.prod_spellbot_password.result}@${var.db_host}:${var.db_port}/${postgresql_database.prod_db.name}"
  })
}
