
output "postgresql_connection" {
  value     = "postgresql://psqladmin:${random_password.postgresql_admin.result}@${azurerm_postgresql_flexible_server.postgresql.fqdn}/postgres"
  sensitive = true
}

output "postgresql_host" {
  value = azurerm_postgresql_flexible_server.postgresql.fqdn
}

output "postgresql_port" {
  value = "5432"
}

output "postgresql_database" {
  value = "postgres"
}

output "postgresql_user" {
  value = "psqladmin"
}

output "postgresql_password" {
  value     = random_password.postgresql_admin.result
  sensitive = true
}

output "ai_search_admin_key" {
  value     = azurerm_search_service.search.primary_key
  sensitive = true
}
output "ai_search_service_id" {
  value = azurerm_search_service.search.id
}
output "ai_search_endpoint" {
  value = "https://${azurerm_search_service.search.name}.search.windows.net"
}