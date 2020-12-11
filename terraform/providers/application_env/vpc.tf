resource "azurerm_resource_group" "vpc" {
  name     = "${var.name}-vpc-${var.deployment_namespace}"
  location = var.deployment_location

  tags = {
    environment = var.deployment_namespace
    owner       = var.owner
  }
}

resource "azurerm_network_ddos_protection_plan" "vpc" {
  count               = var.ddos_enabled
  name                = "${var.name}-ddos-${var.deployment_namespace}"
  location            = azurerm_resource_group.vpc.location
  resource_group_name = azurerm_resource_group.vpc.name
}

resource "azurerm_virtual_network" "vpc" {
  name                = "${var.name}-network-${var.deployment_namespace}"
  location            = azurerm_resource_group.vpc.location
  resource_group_name = azurerm_resource_group.vpc.name
  address_space       = [var.virtual_network] # TODO(jesse) Can this be wired up dynamically?
  dns_servers         = []

  tags = {
    environment = var.deployment_namespace
    owner       = var.owner
  }
}

resource "azurerm_network_watcher" "vpc" {
  name                = "${var.name}-network-watcher-${var.deployment_namespace}"
  location            = azurerm_resource_group.vpc.location
  resource_group_name = azurerm_resource_group.name
}

resource "azurerm_storage_account" "flowlogs_storage" {
  name                      = "nsgflowlogs${var.deployment_namespace}"
  resource_group_name       = azurerm_resource_group.vpc.name
  location                  = azurerm_resource_group.vpc.location
  account_tier              = "Standard"
  account_kind              = "StorageV2"
  account_replication_type  = "LRS"
  enable_https_traffic_only = true
}

resource "azurerm_network_security_group" "logging_nsg" {
   name                = "${var.name}-nsg-${var.deployment_namespace}"
   location            = azurerm_resource_group.vpc.location
   resource_group_name = azurerm_resource_group.vpc.name
   security_rule {
     name                       = "allowAll"
     priority                   = 100
     direction                  = "Inbound"
     access                     = "Allow"
     protocol                   = "Tcp"
     source_port_range          = var.virtual_network
     destination_port_range     = "*"
     source_address_prefix      = "*"
     destination_address_prefix = "*"
   }
   tags = {
     environment = var.deployment_namespace
     owner       = var.owner
   }
 }

resource "azurerm_network_watcher_flow_log" "vpc" {
  network_watcher_name = "${var.name}-network-watcher-${var.deployment_namespace}"
  resource_group_name  = azurerm_resource_group.name
  network_security_group_id = azurerm_network_security_group.logging_nsg.id
  storage_account_id        = azurerm_storage_account.flowlogs_storage.id
  enabled                   = true
  retention_policy {
    enabled = true
    days    = 7
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = var.logging_workspace_id
    workspace_region      = azurerm_resource_group.vpc.location
    workspace_resource_id = var.logging_workspace_resource_id
    interval_in_minutes   = 10
  }
}
