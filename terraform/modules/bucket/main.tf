resource "azurerm_resource_group" "bucket" {
  name     = "${var.name}-${var.service_name}-${var.environment}"
  location = var.region
}

resource "azurerm_storage_account" "bucket" {
  name                     = var.service_name
  resource_group_name      = azurerm_resource_group.bucket.name
  location                 = azurerm_resource_group.bucket.location
  account_tier             = "Standard"
  account_kind             = var.account_kind
  account_replication_type = "LRS"

  blob_properties {
    cors_rule {
      allowed_origins    = ["https://${var.environment}.atat.dev"]
      allowed_methods    = ["OPTIONS", "GET", "PUT"]
      allowed_headers    = ["*"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 200
    }
  }
}

resource "azurerm_storage_account_network_rules" "acls" {
  resource_group_name  = azurerm_resource_group.bucket.name
  storage_account_name = azurerm_storage_account.bucket.name

  default_action = var.policy

  # Azure Storage CIDR ACLs do not accept /32 CIDR ranges.
  ip_rules = [
    for cidr in values(var.whitelist) : cidr
  ]
  virtual_network_subnet_ids = var.subnet_ids
  bypass                     = ["AzureServices"]

}

resource "azurerm_storage_container" "bucket" {
  name                  = var.storage_container_name
  storage_account_name  = azurerm_storage_account.bucket.name
  container_access_type = var.container_access_type
}

resource "azurerm_monitor_diagnostic_setting" "bucket_diagnostic" {
  name                       = "${var.service_name}-bucket-diag-${var.environment}"
  target_resource_id         = azurerm_storage_account.bucket.id
  log_analytics_workspace_id = var.workspace_id

  log {
    category = "StorageRead"
    retention_policy {
      enabled = true
    }
  }
  log {
    category = "StorageWrite"
    retention_policy {
      enabled = true
    }
  }
  log {
    category = "StorageDelete"
    retention_policy {
      enabled = true
    }
  }
  metric {
    category = "Transaction"
    retention_policy {
      enabled = true
    }
  }
}


# Added until requisite TF bugs are fixed. Typically this would be configured in the
# storage_account resource
#resource "null_resource" "retention" {
#  provisioner "local-exec" {
#    command = "az storage logging update --account-name ${azurerm_storage_account.bucket.name} --log rwd --services bqt --retention 90"
#  }
#}
