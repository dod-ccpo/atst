resource "azurerm_resource_group" "app_keyvault" {
  name     = "cz-keyvault-${var.deployment_namespace}"
  location = var.deployment_location
}

resource "azurerm_key_vault" "app_keyvault" {
  name                = "cz-kv-${var.deployment_namespace}"
  location            = azurerm_resource_group.app_keyvault.location
  resource_group_name = azurerm_resource_group.app_keyvault.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  soft_delete_enabled = true

  sku_name = "premium"

  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    virtual_network_subnet_ids = [azurerm_subnet.aks.id, local.deployment_subnet_id]
    ip_rules                   = values({ "operator" = local.operator_ip })
  }

  tags = {
    environment = var.deployment_namespace
    owner       = var.owner
  }
}

resource "time_sleep" "app_keyvault_wait_5" {
  depends_on = [
    azurerm_key_vault.app_keyvault,
    # azurerm_key_vault_access_policy.app_keyvault_tenant_policy,
    azurerm_key_vault_access_policy.app_keyvault_admin_policy,
  ]

  create_duration = "300s"
}

resource "azurerm_key_vault_access_policy" "app_keyvault_k8s_policy" {
  key_vault_id = azurerm_key_vault.app_keyvault.id

  tenant_id = data.azurerm_client_config.current.tenant_id
  object_id = module.keyvault_reader_identity.principal_id

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

# Admin Access
resource "azurerm_key_vault_access_policy" "app_keyvault_admin_policy" {
  # for_each     = var.admin_principals
  key_vault_id = azurerm_key_vault.app_keyvault.id

  tenant_id = data.azurerm_client_config.current.tenant_id
  object_id = data.azurerm_client_config.azure_client.object_id

  key_permissions = [
    "create",
    "delete",
    "get",
    "list",
    "recover",
    "update",
    "restore",
  ]

  secret_permissions = [
    "get",
    "list",
    "set",
    "delete",
    "recover",
    "restore",
  ]

  # backup create delete deleteissuers get getissuers import list listissuers managecontacts manageissuers purge recover restore setissuers update
  certificate_permissions = [
    "backup",
    "create",
    "delete",
    "deleteissuers",
    "get",
    "import",
    "list",
    "listissuers",
    "manageissuers",
    "update",
    "recover",
    "restore",
  ]
}


resource "azurerm_key_vault_key" "app_keyvault_secret_key" {
  name         = "SECRET-KEY"
  key_vault_id = azurerm_key_vault.app_keyvault.id
  key_type     = "RSA"
  key_size     = 2048

  key_opts = [
    "decrypt",
    "encrypt",
    "sign",
    "unwrapKey",
    "verify",
    "wrapKey",
  ]

  depends_on = [time_sleep.app_keyvault_wait_5]
}

resource "azurerm_key_vault_secret" "secret" {
  for_each = merge(var.keyvault_secrets, {
    "AZURE-CLIENT-ID"      = module.tenant_keyvault_app.application_id
    "AZURE-SECRET-KEY"     = module.tenant_keyvault_app.application_password
    "AZURE-STORAGE-KEY"    = module.task_order_bucket.primary_access_key
    "AZURE-TENANT-ID"      = data.azurerm_client_config.azure_client.tenant_id
    "AZURE-USER-OBJECT-ID" = data.azurerm_client_config.azure_client.object_id
    "AZURE-VAULT-URL"      = azurerm_key_vault.tenant_keyvault.vault_uri
    "DHPARAMS"             = file(var.dhparams_path)
    "PGPASSWORD"           = random_password.atat_user_password.result
    "REDIS-PASSWORD"       = azurerm_redis_cache.redis.primary_access_key
    "SAML-IDP-CERT"        = ""
  })

  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.app_keyvault.id
  depends_on   = [time_sleep.app_keyvault_wait_5]
}

resource "random_password" "atat_user_password" {
  length           = 15
  min_numeric      = 0
  special          = false
  override_special = "!"
}

resource "azurerm_key_vault_certificate" "atatdev" {
  name         = "atatdev"
  key_vault_id = azurerm_key_vault.app_keyvault.id
  certificate {
    contents = filebase64(var.tls_cert_path)
    password = ""
  }
  certificate_policy {
    issuer_parameters {
      name = "Unknown"
    }

    key_properties {
      exportable = true
      key_size   = 2048
      key_type   = "RSA"
      reuse_key  = false
    }
    secret_properties {
      content_type = "application/x-pem-file"
    }
  }
  depends_on = [time_sleep.app_keyvault_wait_5]
}

resource "azurerm_key_vault_access_policy" "allow_tenant_keyvault_application_access_to_app_keyvault" {
  key_vault_id = azurerm_key_vault.app_keyvault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = module.tenant_keyvault_app.sp_object_id

  secret_permissions = [
    "get",
    "set",
  ]
}
