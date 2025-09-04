# Database Infrastructure

This Terraform configuration sets up the database infrastructure for SpellBot, including:

- Two PostgreSQL databases (staging and production) on a single PostgreSQL instance
- Two database users (one for each environment)
- Passwords stored securely in AWS Secrets Manager

## Prerequisites

1. A PostgreSQL instance (like AWS RDS/Aurora) already running
2. Root database credentials
3. Terraform installed
4. AWS CLI configured with appropriate permissions

## Setup

1. Copy the example variables file:

   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your actual values:

   ```hcl
   root_db_user     = "postgres"
   root_db_password = "your-actual-root-password"
   db_host         = "your-aurora-cluster.cluster-xxxxx.us-east-1.rds.amazonaws.com"
   db_port         = 5432
   ```

3. Initialize Terraform:

   ```bash
   terraform init
   ```

4. Plan the deployment:

   ```bash
   terraform plan
   ```

5. Apply the configuration:
   ```bash
   terraform apply
   ```

## What gets created

### Databases

- `spellbot_staging` - Database for staging environment
- `spellbot_production` - Database for production environment

### Users

- `spellbot_staging_user` - Database user for staging environment
- `spellbot_production_user` - Database user for production environment

### AWS Secrets Manager

- `spellbot/staging/db-password` - Complete connection info for staging
- `spellbot/production/db-password` - Complete connection info for production

Each secret contains a JSON object with:

```json
{
  "username": "spellbot_staging_user",
  "password": "generated-password",
  "database": "spellbot_staging",
  "host": "your-db-host",
  "port": 5432,
  "DB_URL": "postgresql://spellbot_staging_user:generated-password@your-db-host:5432/spellbot_staging"
}
```

### Permissions

Each spellbot user gets:

- `USAGE` and `CREATE` privileges on the public schema
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` privileges on all tables
- `USAGE` and `SELECT` privileges on all sequences
