data "http" "myip" {
  url = "https://ipinfo.io/ip"
}

data "azurerm_client_config" "current" {}

data "azurerm_client_config" "azure_client" {}

locals {
  deployment_subnet_id            = data.terraform_remote_state.previous_stage.outputs.operations_deployment_subnet_id
  operations_container_registry   = data.terraform_remote_state.previous_stage.outputs.operations_container_registry_login_server
  operations_resource_group_name  = data.terraform_remote_state.previous_stage.outputs.operations_resource_group_name
  operations_storage_account_name = data.terraform_remote_state.previous_stage.outputs.operations_storage_account_name
  operator_ip                     = chomp(data.http.myip.body)
  log_analytics_workspace_id      = data.terraform_remote_state.previous_stage.outputs.logging_workspace_id
}

module "tenant_keyvault_app" {
  source               = "../../modules/azure_ad"
  name                 = "tenant-keyvault"
  deployment_namespace = var.deployment_namespace
}

# Task order bucket is required to be accessible publicly by the users.
# which is why the policy here is "Allow"
module "task_order_bucket" {
  source                 = "../../modules/bucket"
  service_name           = "${var.deployment_namespace}tasks"
  owner                  = var.owner
  name                   = var.name
  environment            = var.deployment_namespace
  region                 = var.deployment_location
  policy                 = "Allow"
  subnet_ids             = [azurerm_subnet.aks.id]
  whitelist              = { "operator" = local.operator_ip }
  storage_container_name = var.task_order_bucket_storage_container_name
  workspace_id           = local.log_analytics_workspace_id
}

module "container_registry" {
  source        = "../../modules/container_registry"
  name          = var.name
  region        = var.deployment_location
  environment   = var.deployment_namespace
  owner         = var.owner
  backup_region = "" # TODO(jesse) Unused.
  policy        = "Allow"
  whitelist     = ["${local.operator_ip}/32"]
  workspace_id  = local.log_analytics_workspace_id
  subnet_list = [
    azurerm_subnet.aks.id,
    azurerm_subnet.mgmt_subnet.id,
  ]
}
