module "aurora_cluster" {
  source = "terraform-aws-modules/rds-aurora/aws"

  name                        = "spellbot-aurora"
  engine                      = "aurora-postgresql"
  engine_version              = "17.5"
  master_username             = "postgres"
  manage_master_user_password = true
  publicly_accessible         = true
  # Use the smallest Aurora instance type
  instances = {
    one = {
      instance_class = "db.t4g.medium"
    }
  }

  # Use database subnets from VPC module
  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group_name
  security_group_rules = {
    database_ingress = {
      source_security_group_id = aws_security_group.ecs_tasks.id
    }
  }

  # Backup configuration
  backup_retention_period      = 7
  preferred_backup_window      = "03:00-06:00"
  preferred_maintenance_window = "Mon:00:00-Mon:03:00"

  # Monitoring
  monitoring_interval = 60

  deletion_protection = false

  # Performance Insights
  performance_insights_enabled = true

}
