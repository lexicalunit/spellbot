# ElastiCache subnet group
resource "aws_elasticache_subnet_group" "main" {
  name       = "spellbot-cache-subnet"
  subnet_ids = module.vpc.elasticache_subnets

  tags = {
    Name = "spellbot-cache-subnet-group"
  }
}

# ElastiCache Valkey cluster - minimal single node
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "spellbot-valkey"
  description          = "SpellBot Valkey cluster"

  # Minimal configuration
  node_type            = "cache.t4g.micro"
  port                 = 6379
  parameter_group_name = "default.valkey7"

  # Single node configuration
  num_cache_clusters = 1

  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.elasticache.id]

  # Backup and maintenance
  snapshot_retention_limit = 1
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:06:00"

  # Disable automatic failover for single node
  automatic_failover_enabled = false
  multi_az_enabled           = false

  # Engine settings
  engine         = "valkey"
  engine_version = "7.2"

  # Disable encryption for cost savings (not recommended for prod)
  at_rest_encryption_enabled = false
  transit_encryption_enabled = false

  tags = {
    Name = "spellbot-valkey"
  }
}
