# Infrastructure

Infrastructure for SpellBot is managed by Terraform. Changes to the infrastructure are deployed manually by running `terraform apply` commands locally. Changes to the source code are deployed automatically by GitHub Actions.

## Verifying changes

Please verify changes using [`tflint`][tflint] before committing.

```sh
tflint --chdir infrastructure/app --minimum-failure-severity=error
tflint --chdir infrastructure/db --minimum-failure-severity=error
tflint --chdir infrastructure/o11y --minimum-failure-severity=error
```

## Application (app)

The `app` directory contains the Terraform configuration for the SpellBot application. This includes the AWS resources necessary to run and monitor the application, such as the database resources, ECS cluster, services, and task definitions. etc...

### Application setup

```sh
terraform -chdir=infrastructure/app init   # only needed once
terraform -chdir=infrastructure/app plan   # optional: verify changes
terraform -chdir=infrastructure/app apply  # apply changes (will prompt for confirmation)
```

## Observability (o11y)

The `o11y` directory contains the Terraform configuration for SpellBot observability. This includes datadog monitors, dashboards, etc...

### Observability setup

First copy the example variables file:

```sh
cp infrastructure/o11y/terraform.tfvars.example infrastructure/o11y/terraform.tfvars
```

Then edit `infrastructure/o11y/terraform.tfvars` to replace the placeholder values with your actual values.

Finally, run the following commands:

```sh
terraform -chdir=infrastructure/o11y init   # only needed once
terraform -chdir=infrastructure/o11y plan   # optional: verify changes
terraform -chdir=infrastructure/o11y apply  # apply changes (will prompt for confirmation)
```

## Database (db)

This Terraform configuration sets up the database infrastructure for SpellBot, including:

- Two PostgreSQL databases (stage and prod) on a single PostgreSQL instance
- Two database users (one for each environment)
- Passwords stored securely in AWS Secrets Manager

### Database prerequisites

1. A PostgreSQL instance (like AWS RDS/Aurora) already running
2. Root database credentials
3. Terraform installed
4. AWS CLI configured with appropriate permissions

### Database setup

Firs copy the example variables file:

```sh
cp infrastructure/db/terraform.tfvars.example infrastructure/db/terraform.tfvars
```

Then edit `infrastructure/db/terraform.tfvars` to replace the placeholder values with your actual values.

Finally, run the following commands:

```sh
terraform -chdir=infrastructure/db init   # only needed once
terraform -chdir=infrastructure/db plan   # optional: verify changes
terraform -chdir=infrastructure/db apply  # apply changes (will prompt for confirmation)
```

### What gets created

#### Databases

- `spellbot_stage` - Database for stage environment
- `spellbot_prod` - Database for prod environment

#### Users

- `spellbot_stage_user` - Database user for stage environment
- `spellbot_prod_user` - Database user for prod environment

#### AWS Secrets Manager

- `spellbot/stage/db-password` - Complete connection info for stage
- `spellbot/prod/db-password` - Complete connection info for prod

Each secret contains a JSON object with:

```json
{
  "username": "spellbot_ENV_user",
  "password": "generated-password",
  "database": "spellbot_ENV",
  "host": "your-db-host",
  "port": 5432,
  "DB_URL": "postgresql://spellbot_ENV_user:generated-password@your-db-host:5432/spellbot_ENV"
}
```

#### Permissions

Each spellbot user gets:

- `USAGE` and `CREATE` privileges on the public schema
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` privileges on all tables
- `USAGE` and `SELECT` privileges on all sequences

[tflint]: https://github.com/terraform-linters/tflint
