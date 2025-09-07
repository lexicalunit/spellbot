variable "root_db_user" {
  description = "Root database username"
  type        = string
  default     = "postgres"
}

variable "root_db_password" {
  description = "Root database password"
  type        = string
  sensitive   = true
}

variable "db_host" {
  description = "Database host"
  type        = string
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}
