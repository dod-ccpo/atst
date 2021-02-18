variable "region" {
  type        = string
  description = "Region this module and resources will be created in"
}

variable "name" {
  type        = string
  description = "Unique name for the services in this module"
}

variable "environment" {
  type        = string
  description = "Environment these resources reside (prod, dev, staging, etc)"
}

variable "owner" {
  type        = string
  description = "Owner of the environment and resources created in this module"
}

variable "container_access_type" {
  default     = "private"
  description = "Access type for the container (Default: private)"
  type        = string

}

variable "service_name" {
  description = "Name of the service using this bucket"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet_ids that will have access to this service"
  type        = list
}

variable "policy" {
  description = "The default policy for the network access rules (Allow/Deny)"
  default     = "Deny"
  type        = string
}

variable "whitelist" {
  type        = map
  description = "A map of whitelisted IPs and CIDR ranges. For single IPs, Azure expects just the IP, NOT a /32."
  default     = {}
}



variable "account_kind" {
  type        = string
  description = "Type of storage account"
  default     = "Storage"

}

variable "storage_container_name" {
  type        = string
  description = "What to name the created storage container"
}

variable "workspace_id" {
  description = "The Log Analytics Workspace ID"
  type        = string
}