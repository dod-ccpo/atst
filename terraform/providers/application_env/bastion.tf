module "bastion_sp" {
  source               = "../../modules/azure_ad"
  name                 = "bastion-service-principal"
  deployment_namespace = var.deployment_namespace
}
resource "azurerm_resource_group" "bastion" {
  name     = "${var.name}-bastion-${var.deployment_namespace}"
  location = var.deployment_location
}

# add mgmgt subnet
resource "azurerm_subnet" "mgmt_subnet" {
  name                 = "mgmt-subnet"
  resource_group_name  = azurerm_resource_group.vpc.name
  virtual_network_name = azurerm_virtual_network.vpc.name
  address_prefixes     = ["10.1.250.0/24"]

  enforce_private_link_endpoint_network_policies = true

  service_endpoints = [
    "Microsoft.ContainerRegistry",
    "Microsoft.KeyVault",
    "Microsoft.Sql",
    "Microsoft.Storage"
  ]

  delegation {
    name = "delegation"

    service_delegation {
      name    = "Microsoft.ContainerInstance/containerGroups"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_network_profile" "bastion" {
  name                = "bastion-net-profile"
  location            = azurerm_resource_group.bastion.location
  resource_group_name = azurerm_resource_group.bastion.name

  container_network_interface {
    name = "bastionnic"

    ip_configuration {
      name      = "bastionipconfig"
      subnet_id = azurerm_subnet.mgmt_subnet.id
    }
  }
  depends_on = [azurerm_subnet.mgmt_subnet]
}

# Bastion
resource "azurerm_container_group" "bastion" {
  name                = "${var.name}-bastion-${var.deployment_namespace}"
  location            = azurerm_resource_group.bastion.location
  resource_group_name = azurerm_resource_group.bastion.name
  ip_address_type     = "private"
  network_profile_id  = azurerm_network_profile.bastion.id
  os_type             = "Linux"

  container {
    name     = "bastion"
    image    = "${local.operations_container_registry}/ops:latest"
    cpu      = "1"
    memory   = "2"
    commands = ["tail","-f","/var/log/snoopy.log"]

    ports {
      port     = 443
      protocol = "TCP"
    }

    secure_environment_variables = {
      "SP_CLIENT_ID"        = var.operator_client_id
      "SP_CLIENT_SECRET"    = var.operator_client_secret
      "TENANT_ID"           = var.operator_tenant_id
      "SUBSCRIPTION_ID"     = var.operator_subscription_id
      "OPS_REGISTRY"        = local.operations_container_registry
      "ATAT_REGISTRY"       = module.container_registry.container_registry_name
      "NAMESPACE"           = var.deployment_namespace
      "OPS_RESOURCE_GROUP"  = local.operations_resource_group_name
      "OPS_STORAGE_ACCOUNT" = local.operations_storage_account_name
    }
  }

  image_registry_credential {
    username = var.operator_client_id
    password = var.operator_client_secret
    server   = local.operations_container_registry
  }

  diagnostics {
    log_analytics {
      workspace_id = local.log_analytics_workspace_uuid
      workspace_key = local.log_analytics_workspace_key
    }
  }

  tags = {
    environment = "testing"
  }
}
