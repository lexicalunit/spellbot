
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
resource "random_password" "staging_spellbot_password" {
  length  = 32
  special = false
}

resource "random_password" "production_spellbot_password" {
  length  = 32
  special = false
}

# Create databases
resource "postgresql_database" "staging_db" {
  name  = "spellbot_staging"
  owner = var.root_db_user
}

resource "postgresql_database" "production_db" {
  name  = "spellbot_production"
  owner = var.root_db_user
}

# Create staging spellbot user
resource "postgresql_role" "staging_spellbot_user" {
  name     = "spellbot_staging_user"
  login    = true
  password = random_password.staging_spellbot_password.result
}

# Create production spellbot user
resource "postgresql_role" "production_spellbot_user" {
  name     = "spellbot_production_user"
  login    = true
  password = random_password.production_spellbot_password.result
}

# Grant privileges on staging database
resource "postgresql_grant" "staging_db_privileges" {
  database    = postgresql_database.staging_db.name
  role        = postgresql_role.staging_spellbot_user.name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "staging_table_privileges" {
  database    = postgresql_database.staging_db.name
  role        = postgresql_role.staging_spellbot_user.name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_grant" "staging_sequence_privileges" {
  database    = postgresql_database.staging_db.name
  role        = postgresql_role.staging_spellbot_user.name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]
}

# Grant privileges on production database
resource "postgresql_grant" "production_db_privileges" {
  database    = postgresql_database.production_db.name
  role        = postgresql_role.production_spellbot_user.name
  schema      = "public"
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "production_table_privileges" {
  database    = postgresql_database.production_db.name
  role        = postgresql_role.production_spellbot_user.name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT", "INSERT", "UPDATE", "DELETE"]
}

resource "postgresql_grant" "production_sequence_privileges" {
  database    = postgresql_database.production_db.name
  role        = postgresql_role.production_spellbot_user.name
  schema      = "public"
  object_type = "sequence"
  privileges  = ["USAGE", "SELECT"]
}

# Store passwords in AWS Secrets Manager
resource "aws_secretsmanager_secret" "staging_spellbot_password" {
  name        = "spellbot/staging/db-details"
  description = "Password for staging spellbot database user"

  tags = {
    Environment = "staging"
    Component   = "database"
  }
}

resource "aws_secretsmanager_secret_version" "staging_spellbot_password" {
  secret_id = aws_secretsmanager_secret.staging_spellbot_password.id
  secret_string = jsonencode({
    username = postgresql_role.staging_spellbot_user.name
    password = random_password.staging_spellbot_password.result
    database = postgresql_database.staging_db.name
    host     = var.db_host
    port     = var.db_port
    DB_URL   = "postgresql://${postgresql_role.staging_spellbot_user.name}:${random_password.staging_spellbot_password.result}@${var.db_host}:${var.db_port}/${postgresql_database.staging_db.name}"
  })
}

resource "aws_secretsmanager_secret" "production_spellbot_password" {
  name        = "spellbot/production/db-details"
  description = "Password for production spellbot database user"

  tags = {
    Environment = "production"
    Component   = "database"
  }
}

resource "aws_secretsmanager_secret_version" "production_spellbot_password" {
  secret_id = aws_secretsmanager_secret.production_spellbot_password.id
  secret_string = jsonencode({
    username = postgresql_role.production_spellbot_user.name
    password = random_password.production_spellbot_password.result
    database = postgresql_database.production_db.name
    host     = var.db_host
    port     = var.db_port
    DB_URL   = "postgresql://${postgresql_role.production_spellbot_user.name}:${random_password.production_spellbot_password.result}@${var.db_host}:${var.db_port}/${postgresql_database.production_db.name}"
  })
}


