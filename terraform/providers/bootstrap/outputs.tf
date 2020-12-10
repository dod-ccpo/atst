output "operations_container_registry_name" {
  value       = azurerm_container_registry.operations_container_registry.name
  description = "Global registry so that docker images can be reused across deployments."
}

output "operations_container_registry_login_server" {
  value       = azurerm_container_registry.operations_container_registry.login_server
  description = "The URL that can be used to log into the container registry."
}

output "operations_virtual_network" {
  value       = azurerm_virtual_network.operations_virtual_network.name
  description = "Name of the virtual network that houses our deployment subnet"
}

output "operations_deployment_subnet_id" {
  value       = azurerm_subnet.deployment_subnet.id
  description = "ID of the subnet all subsequent resources are deployed into."
}

output "operations_resource_group_name" {
  value       = azurerm_resource_group.operations_resource_group.name
  description = "Resource group containing all operations resources."
}

output "operations_tf_bootstrap_container_name" {
  value       = azurerm_storage_container.tf_bootstrap.name
  description = "Name of the container in the storage account used to hold deployment terraform states."
}

output "operations_tf_application_container_name" {
  value       = azurerm_storage_container.tf_application.name
  description = "Name of the container in the storage account used to hold deployment terraform states."
}

output "operations_config_container_name" {
  value       = azurerm_storage_container.config.name
  description = "Name of the container in the storage account used to hold certs and config files."
}

output "operations_storage_account_name" {
  value       = azurerm_storage_account.operations_storage_account.name
  description = "Global storage for deployments to store their configurations and states."
}

output "namespace" {
  value       = var.namespace
  description = "Namespace for this deployment - Less than 5 characters, lower case"
}

output "logging_workspace_resource_id" {
  value = azurerm_log_analytics_workspace.log_workspace.id
  description = "the id of the log workspace itself"
}

output "logging_workspace_id" {
  value = azurerm_log_analytics_workspace.log_workspace.workspace_id
  description = "the workspace id of the log workspace"
}

output "logging_workspace_uuid" {
  value       = azurerm_log_analytics_workspace.log_workspace.workspace_id
  description = "Primary Key of the Log Analytics Workspace"
}

output "logging_workspace_primary_key" {
  value       = azurerm_log_analytics_workspace.log_workspace.primary_shared_key
  description = "Primary Key of the Log Analytics Workspace"
}
