resource "azurerm_resource_group" "tenant_keyvault" {
  name     = "tenants-keyvault-${var.deployment_namespace}"
  location = var.deployment_location
}

resource "azurerm_key_vault" "tenant_keyvault" {
  name                = "tenants-kv-${var.deployment_namespace}"
  location            = azurerm_resource_group.tenant_keyvault.location
  resource_group_name = azurerm_resource_group.tenant_keyvault.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  workspace_id        = var.logging_workspace_id
  soft_delete_enabled = true

  sku_name = "premium"

  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    virtual_network_subnet_ids = [azurerm_subnet.aks.id]
    ip_rules                   = ["${local.operator_ip}/32"]
  }

  tags = {
    environment = var.deployment_namespace
    owner       = var.owner
  }
}

resource "time_sleep" "tenant_keyvault_wait_5" {
  depends_on = [
    azurerm_key_vault.tenant_keyvault,
    azurerm_key_vault_access_policy.tenant_keyvault_policy,
  ]

  create_duration = "300s"
}

resource "azurerm_key_vault_access_policy" "tenant_keyvault_k8s_policy" {
  # This was defaulting to 0, which would block this policy from being
  # created, but it seems essential so I'm leaving it in.
  # count        = var.principal_id_count
  key_vault_id = azurerm_key_vault.tenant_keyvault.id

  tenant_id = data.azurerm_client_config.current.tenant_id
  object_id = data.azurerm_client_config.azure_client.object_id

  key_permissions = [
    "get",
  ]

  secret_permissions = [
    "get",
  ]

  certificate_permissions = [
    "get"
  ]

}


resource "azurerm_key_vault_access_policy" "tenant_keyvault_policy" {
  key_vault_id = azurerm_key_vault.tenant_keyvault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = module.tenant_keyvault_app.sp_object_id

  key_permissions = []

  secret_permissions = [
    "get",
    "list",
    "set",
    "delete"
  ]

  certificate_permissions = [
    "get"
  ]
}
