resource "azurerm_resource_group" "operations_resource_group" {
  name     = "cloudzero-ops-${var.namespace}"
  location = var.operations_location
}

resource "azurerm_virtual_network" "operations_virtual_network" {
  name                = "cloudzero-ops-network-${var.namespace}"
  location            = var.operations_location
  resource_group_name = azurerm_resource_group.operations_resource_group.name
  address_space       = ["10.0.0.0/16"]
}

resource "azurerm_subnet" "deployment_subnet" {
  name                 = "deployment-subnet"
  address_prefixes     = ["10.0.1.0/24"]
  resource_group_name  = azurerm_resource_group.operations_resource_group.name
  virtual_network_name = azurerm_virtual_network.operations_virtual_network.name

  service_endpoints = [
    "Microsoft.ContainerRegistry",
    "Microsoft.KeyVault",
    "Microsoft.Sql",
    "Microsoft.Storage"
  ]

  delegation {
    name = "Microsoft.ContainerInstance.containerGroups"

    service_delegation {
      name    = "Microsoft.ContainerInstance/containerGroups"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_storage_account" "operations_storage_account" {
  name                     = "czopsstorageaccount${var.namespace}"
  resource_group_name      = azurerm_resource_group.operations_resource_group.name
  location                 = var.operations_location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
resource "azurerm_storage_container" "tf_bootstrap" {
  name                 = "tf-bootstrap"
  storage_account_name = azurerm_storage_account.operations_storage_account.name
}
resource "azurerm_storage_container" "tf_application" {
  name                 = "tf-application"
  storage_account_name = azurerm_storage_account.operations_storage_account.name
}

resource "azurerm_storage_container" "config" {
  name                 = "config"
  storage_account_name = azurerm_storage_account.operations_storage_account.name
}

resource "azurerm_container_registry" "operations_container_registry" {
  name                = "cloudzeroopsregistry${var.namespace}"
  resource_group_name = azurerm_resource_group.operations_resource_group.name
  location            = var.operations_location
  sku                 = "Premium"
}

resource "azurerm_monitor_diagnostic_setting" "bucket_diagnostic" {
  name                       = "czopsstorageaccount-bucket-diag-${var.namespace}"
  target_resource_id         = "${azurerm_storage_account.operations_storage_account.id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_workspace.id

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

# resource "azurerm_monitor_diagnostic_setting" "ops_acr_diagnostic" {
#   name                       = "${var.namespace}-ops-acr-diag"
#   target_resource_id         = azurerm_container_registry.operations_container_registry.id
#   log_analytics_workspace_id = module.logs.workspace_id
#   log {
#     category = "ContainerRegistryRepositoryEvents"
#     retention_policy {
#       enabled = true
#     }
#   }
#   log {
#     category = "ContainerRegistryLoginEvents"
#     retention_policy {
#       enabled = true
#     }
#   }
#   metric {
#     category = "AllMetrics"
#     retention_policy {
#       enabled = true
#     }
#   }
# }


resource "local_file" "self_remote_backend" {
  content = templatefile("templates/versions.override.tf.tmpl", {
    backend_resource_group_name  = azurerm_resource_group.operations_resource_group.name
    backend_storage_account_name = azurerm_storage_account.operations_storage_account.name
    backend_state_container_name = azurerm_storage_container.tf_bootstrap.name
    backend_state_container_key  = "terraform.tfstate"
  })

  filename = "versions.override.tf"
}


resource "azurerm_resource_group" "log_workspace" {
  name     = "${var.namespace}-log-workspace"
  location = var.operations_location
}

resource "azurerm_log_analytics_workspace" "log_workspace" {
  name                = "cloudzero-${var.namespace}-log-workspace"
  location            = azurerm_resource_group.log_workspace.location
  resource_group_name = azurerm_resource_group.log_workspace.name
  sku                 = "Premium"
  retention_in_days   = 365
  tags = {
    environment = var.namespace
    owner       = var.operator_client_id
  }
}
