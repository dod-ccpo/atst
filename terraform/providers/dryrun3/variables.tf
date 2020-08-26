variable "environment" {}
variable "lifecycle_env_name" {
default = "staging"
}

variable "region" {}

variable "backup_region" {}

variable "bastion_resource_group" {}
variable "bastion_aks_sp_secret" {}
variable "bastion_aks_sp_id" {}
variable "bastion_ssh_pub_key_path" {}

variable "owner" {}

variable "name" {}

variable "virtual_network" {}

variable "networks" {
  type = map
}

variable "service_endpoints" {
  type = map
}

variable "route_tables" {
  description = "Route tables and their default routes"
  type        = map
}

# Custom routes
variable "routes" {
  description = "Routes for next hop types: VirtualNetworkGateway, VnetLocal, Internet or None"
  type        = map
}

variable "dns_servers" {
  type = list
}

variable "k8s_node_size" {}

variable "k8s_dns_prefix" {}

variable "k8s_autogenerated_route_table_name" {}

variable "tenant_id" {}

variable "admin_users" {
  type = map
}

variable "admin_user_whitelist" {
  type = map
}

variable "storage_admin_whitelist" {
  type = map
}

variable "vpn_client_cidr" {
  type = list
}

variable "bucket_cors_properties" {
  type        = list(map(string))
  description = "supports cors"
  default     = []
}

variable "log_analytics_workspace_id" {}

variable "k8s_resource_group" {}

variable "private_k8s_subnet_cidr" {}

variable "private_aks_service_dns" {}

variable "private_aks_service_cidr" {}

variable "private_aks_docker_bridge_cidr" {}

variable "aks_ssh_pub_key_path" {}

variable "private_aks_sp_secret" {}

variable "private_aks_sp_id" {}

variable "aks_max_node_count" {
  default = 5
}

variable "aks_min_node_count" {
  default = 3
}
variable "postgres_admin_login" {}

variable "task_order_bucket_storage_container_name" {
  default = "task-order-pdfs"
}

variable "tf_state_storage_container_name" {
  default = "tfstate"
}

variable "OPS_CID" {}
variable "OPS_SEC" {}
variable "OPS_OID" {}
