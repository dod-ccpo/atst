module "aks_sp" {
  source               = "../../modules/azure_ad"
  name                 = "aks-service-principal"
  deployment_namespace = var.deployment_namespace
}

resource "azurerm_subnet" "aks" {
  name                                           = "${var.name}-aks-${var.deployment_namespace}"
  resource_group_name                            = azurerm_resource_group.vpc.name
  virtual_network_name                           = azurerm_virtual_network.vpc.name
  address_prefixes                               = ["10.1.2.0/24"]
  enforce_private_link_endpoint_network_policies = false
  service_endpoints = [
    "Microsoft.Storage",
    "Microsoft.KeyVault",
    "Microsoft.ContainerRegistry",
    "Microsoft.Sql"
  ]
}

resource "azurerm_subnet_network_security_group_association" "mgmt_subnet" {
  subnet_id                 = azurerm_subnet.aks.id
  network_security_group_id = azurerm_network_security_group.logging_nsg.id
}

resource "azurerm_route_table" "aks" {
  name                = "${var.name}-aks-${var.deployment_namespace}"
  location            = azurerm_resource_group.vpc.location
  resource_group_name = azurerm_resource_group.vpc.name
}
resource "azurerm_subnet_route_table_association" "aks" {
  subnet_id      = azurerm_subnet.aks.id
  route_table_id = azurerm_route_table.aks.id
}

resource "azurerm_route" "aks_firewall_to_internet" {
  name                = "to-internet"
  resource_group_name = azurerm_resource_group.vpc.name
  route_table_name    = azurerm_route_table.aks.name
  address_prefix      = "${azurerm_public_ip.firewall_ip.ip_address}/32"
  next_hop_type       = "Internet"
}

resource "azurerm_route" "aks_to_fw" {
  name                   = "to-fw"
  resource_group_name    = azurerm_resource_group.vpc.name
  route_table_name       = azurerm_route_table.aks.name
  address_prefix         = "0.0.0.0/0"
  next_hop_type          = "VirtualAppliance"
  next_hop_in_ip_address = azurerm_firewall.fw.ip_configuration[0].private_ip_address
}
resource "azurerm_kubernetes_cluster" "k8s_private" {
  name                    = "${var.name}-private-k8s-${var.deployment_namespace}"
  location                = var.deployment_location
  resource_group_name     = azurerm_resource_group.vpc.name
  dns_prefix              = "atat-aks"
  private_cluster_enabled = true
  node_resource_group     = "${azurerm_resource_group.vpc.name}-private-aks-node-rgs"
  addon_profile {
    azure_policy {
      enabled = true
    }
    kube_dashboard {
      enabled = false
    }
    oms_agent {
      enabled                    = true
      log_analytics_workspace_id = local.log_analytics_workspace_id
    }
  }
  network_profile {
    network_plugin     = "azure"
    dns_service_ip     = var.private_aks_service_dns
    docker_bridge_cidr = var.private_aks_docker_bridge_cidr
    outbound_type      = "userDefinedRouting"
    service_cidr       = var.private_aks_service_cidr
    load_balancer_sku  = "Standard"
  }
  service_principal {
    client_id     = module.aks_sp.sp_client_id
    client_secret = module.aks_sp.service_principal_password
  }

  default_node_pool {
    name                  = "default"
    vm_size               = "Standard_B2s"
    os_disk_size_gb       = 30
    vnet_subnet_id        = azurerm_subnet.aks.id
    enable_node_public_ip = false
    enable_auto_scaling   = false
    node_count            = 3
  }

  lifecycle {
    ignore_changes = [
      default_node_pool.0.node_count
    ]
  }

  tags = {
    Name        = "private-aks-atat"
    environment = var.deployment_namespace
    owner       = var.owner
  }
  depends_on = [
    module.keyvault_reader_identity,
    azurerm_subnet_route_table_association.azure_firewall,
    module.keyvault_reader_identity
  ]
}

module "keyvault_reader_identity" {
  source      = "../../modules/managed_identity"
  name        = var.name
  owner       = var.owner
  environment = var.deployment_namespace
  region      = var.deployment_location
  identity    = "${var.name}-${var.deployment_namespace}-vault-reader"
  roles       = ["Reader", "Managed Identity Operator"]
}
