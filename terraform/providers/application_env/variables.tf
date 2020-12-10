variable "deployment_location" {
  type        = string
  description = "Azure region in which deployment resources are provisioned."
  default     = "East US"
}

variable "region" {
  type        = string
  description = "Azure region in which deployment resources are provisioned - short name"
  default     = "eastus"
}

variable "deployment_namespace" {
  type        = string
  description = "Namespace of provisioned deployment resources."
}

variable "owner" {
  type        = string
  default     = "promptworks"
  description = "TODO(jesse) Is this a required property in all those modules?"
}

variable "name" {
  type        = string
  default     = "cloudzero"
  description = "TODO(jesse) Is this a required property in all those modules?"
}

variable "virtual_network" {
  type        = string
  description = "A mask determining the size (range) of IP addresses for the VPC virtual network."
  default     = "10.1.0.0/16"
}

variable "private_aks_service_dns" {
  default = "10.254.253.10"
}

variable "private_aks_service_cidr" {
  default = "10.254.253.0/24"
}

variable "private_aks_docker_bridge_cidr" {
  default = "172.17.0.1/16"
}

variable "task_order_bucket_storage_container_name" {
  type        = string
  description = ""
  default     = "task-order-pdfs"
}

variable "tls_cert_path" {
  type        = string
  description = "Long-lived certificate for atat.dev and *.atat.dev."
  default     = "/tmp/atatdev.pem"
}

variable "dhparams_path" {
  type        = string
  description = "Long-lived certificate for hyper-securing our session encryption"
  default     = "/tmp/dhparams.pem"
}

variable "keyvault_secrets" {
  type        = map
  description = "Variables used to configure the kubernetes cluster, loaded into keyvault."
}

variable "operator_subscription_id" {
  type        = string
  description = "Subscription ID of the service principle performing the deployment."
}

variable "operator_client_id" {
  type        = string
  description = "Application ID of the service principle performing the deployment."
}

variable "operator_client_secret" {
  type        = string
  description = "Password of the service principle performing the deployment."
}

variable "operator_tenant_id" {
  type        = string
  description = "Tenant ID of the service principle performing the deployment."
}

variable "ops_resource_group" {
  type        = string
  description = "Name of resource group containing resources spun up in the previous bootstrapping stage."
}

variable "ops_storage_account" {
  type        = string
  description = "Name of storage account the containing the terraform state of the previous bootstrapping stage."
}

variable "tf_bootstrap_container" {
  type        = string
  description = "Name of container in the `ops_storage_account` containing the previous stage's terraform state."
}

variable "ddos_enabled" {
  description = "Enable or disable DDoS Protection (1,0)"
  default     = "0"
}

variable "aks_internal_lb_ip" {
  type        = string
  description = "The IP of the loadbalancer that will be created by k8s"
  default     = "10.1.2.201"
}

variable "maintenance_page_ip" {
  type        = string
  description = "The IP of the loadbalancer that will be created by k8s"
  default     = "10.1.2.203"
}
variable "logging_workspace_id" {
  type        = string
  description = "We create a logging workspace in phase1 to log everything. This is it's workspace_id"
}
variable "logging_workspace_resource_id" {
  type        = string
  description = "We create a logging workspace in phase1 to log everything. This is its id"
}
