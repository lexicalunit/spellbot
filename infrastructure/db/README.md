# Database Infrastructure

This Terraform configuration sets up the database infrastructure for SpellBot, including:

- Two PostgreSQL databases (stage and prod) on a single PostgreSQL instance
- Two database users (one for each environment)
- Passwords stored securely in AWS Secrets Manager

## Prerequisites

1. A PostgreSQL instance (like AWS RDS/Aurora) already running
2. Root database credentials
3. Terraform installed
4. AWS CLI configured with appropriate permissions

## Setup

1. Copy the example variables file:

   ```sh
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

   ```sh
   terraform init
   ```

4. Plan the deployment:

   ```sh
   terraform plan
   ```

5. Apply the configuration:

   ```sh
   terraform apply
   ```

## What gets created

### Databases

- `spellbot_stage` - Database for stage environment
- `spellbot_prod` - Database for prod environment

### Users

- `spellbot_stage_user` - Database user for stage environment
- `spellbot_prod_user` - Database user for prod environment

### AWS Secrets Manager

- `spellbot/stage/db-password` - Complete connection info for stage
- `spellbot/prod/db-password` - Complete connection info for prod

Each secret contains a JSON object with:

```json
{
  "username": "spellbot_stage_user",
  "password": "generated-password",
  "database": "spellbot_stage",
  "host": "your-db-host",
  "port": 5432,
  "DB_URL": "postgresql://spellbot_stage_user:generated-password@your-db-host:5432/spellbot_stage"
}
```

### Permissions

Each spellbot user gets:

- `USAGE` and `CREATE` privileges on the public schema
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` privileges on all tables
- `USAGE` and `SELECT` privileges on all sequences
