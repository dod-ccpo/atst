module "keyvault" {
  source       = "../../modules/keyvault"
  name         = var.name
  region       = var.region
  owner        = var.owner
  environment  = var.environment
  tenant_id    = var.tenant_id
  principal_id = module.k8s.principal_id
}
