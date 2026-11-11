# Managed Postgres for Clinical_Case_har (rel.backup_configured).
#
# Replaces the docker-compose `postgres` container (local named volume, no
# backups) for deployed environments with Azure Database for PostgreSQL
# Flexible Server, which provides:
#   - automated daily backups, retained for 35 days (backup_retention_days)
#   - point-in-time recovery (PITR) to any second inside that 35-day window
#   - geo-redundant backup storage, replicated to the Azure paired region so
#     a backup survives loss of the primary region
#
# Restore procedure: docs/runbooks/db-restore.md. Test it at least once
# before go-live.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "resource_group_name" {
  description = "Resource group that holds the Postgres server."
  type        = string
  default     = "rg-clinical-case-har"
}

variable "location" {
  description = "Azure region for the primary server. Pick a region that has an Azure paired region, otherwise geo-redundant backup is not available."
  type        = string
}

variable "postgres_server_name" {
  description = "Name of the Postgres Flexible Server."
  type        = string
  default     = "psql-clinical-case-har"
}

variable "postgres_database_name" {
  description = "Application database name (maps to POSTGRES_DB)."
  type        = string
  default     = "clinical_case_finder"
}

variable "postgres_admin_login" {
  description = "Administrator login (maps to POSTGRES_USER)."
  type        = string
}

variable "postgres_admin_password" {
  description = "Administrator password (maps to POSTGRES_PASSWORD). Supply through TF_VAR_postgres_admin_password or a secret store; never commit it."
  type        = string
  sensitive   = true
}

variable "postgres_sku_name" {
  description = "Compute SKU for the server."
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "postgres_storage_mb" {
  description = "Allocated storage in MB."
  type        = number
  default     = 32768
}

variable "backup_retention_days" {
  description = "Automated backup and PITR retention in days. Must be at least 30 (compliance requirement rel.backup_configured); Azure allows at most 35."
  type        = number
  default     = 35

  validation {
    condition     = var.backup_retention_days >= 30 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 30 and 35."
  }
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = var.postgres_server_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # Same major version as the docker-compose `postgres:16` image.
  version    = "16"
  sku_name   = var.postgres_sku_name
  storage_mb = var.postgres_storage_mb

  administrator_login    = var.postgres_admin_login
  administrator_password = var.postgres_admin_password

  # Automated backups + PITR window (30 days minimum, 35 by default).
  backup_retention_days = var.backup_retention_days

  # Copy backups to the Azure paired region (separate region from the
  # primary). This can only be set when the server is created.
  geo_redundant_backup_enabled = true

  lifecycle {
    # Losing this server would also lose its backups' source; guard it.
    prevent_destroy = true
    # Azure may assign a zone on creation; don't fight it on later plans.
    ignore_changes = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.postgres_database_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

output "postgres_host" {
  description = "Value for POSTGRES_HOST."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgres_backup_retention_days" {
  value = azurerm_postgresql_flexible_server.main.backup_retention_days
}

output "postgres_geo_redundant_backup_enabled" {
  value = azurerm_postgresql_flexible_server.main.geo_redundant_backup_enabled
}
