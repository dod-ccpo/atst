#!/bin/bash
set -x
set -e

[ ! -f service_principal.json ] && ./create-service-principle.sh
sp=$(cat service_principal.json)

echo "exporting terraform creds"
export ARM_CLIENT_ID=$(echo $sp | jq -r '.appId')
export ARM_CLIENT_SECRET=$(echo $sp | jq -r '.password')
export ARM_SUBSCRIPTION_ID=$(az account show --query id --output tsv)
export ARM_TENANT_ID=$(echo $sp | jq -r '.tenant')
export TF_VAR_operator_subscription_id=$ARM_SUBSCRIPTION_ID
export TF_VAR_operator_client_id=$ARM_CLIENT_ID
export TF_VAR_operator_client_secret=$ARM_CLIENT_SECRET
export TF_VAR_operator_tenant_id=$ARM_TENANT_ID

echo "Terraform Bootstrap New Tenant"
cd ../../terraform/providers/bootstrap
terraform init
terraform plan -var "namespace=$1" -out out.plan .
terraform apply out.plan

echo "Now copying this state to the remote"
terraform init -force-copy
terraform refresh -var "namespace=$1"

export REGISTRY_NAME=$(terraform output -raw operations_container_registry_login_server)
export TF_VAR_resource_group_name=$(terraform output -raw operations_resource_group_name)
export TF_VAR_storage_account_name=$(terraform output -raw operations_storage_account_name)
export SUBNET_ID=$(terraform output -raw operations_deployment_subnet_id)
export OPERATIONS_VIRTUAL_NETWORK=$(terraform output -raw operations_virtual_network)
export LOGGING_WORKSPACE_ID=$(terraform output -raw logging_workspace_id)
export LOGGING_WORKSPACE_RESOURCE_ID=$(terraform output -raw logging_workspace_resource_id)


# Now, need to lock that folder down to just the subnet that was created.
# TODO: At the moment, leaving this off because the mgmt_subnet that will be created in phase2 will need access, but we can not grant that until it exists.
# az storage account update --resource-group ${TF_VAR_resource_group_name} --name ${TF_VAR_storage_account_name} --default-action Deny
# az storage account network-rule add --resource-group ${TF_VAR_resource_group_name} --account-name ${TF_VAR_storage_account_name} --subnet ${SUBNET_ID}

echo "Building RHEL"
cd ../../../../atat-rhel-image
make run-build-push-task

echo "Building Python Base"
cd ../atat
az acr build --registry ${REGISTRY_NAME} \
  --build-arg IMAGE=${REGISTRY_NAME}/rhelubi:8.3 \
  --build-arg "redhat_username=$2" \
  --build-arg "redhat_password=$3" \
  --image rhel-py \
  --file python.Dockerfile \
  .

echo "Build Ops Dockerfile"
export COMMIT_SHA=$(git rev-parse HEAD)
az acr build --registry ${REGISTRY_NAME} \
  --build-arg IMAGE=${REGISTRY_NAME}/rhel-py:latest \
  --image ops:${COMMIT_SHA} \
  --image ops:latest \
  --file ops.Dockerfile \
  .


az container create \
  --resource-group ${TF_VAR_resource_group_name} \
  --name "$1-provisioner" \
  --ip-address Private \
  --vnet ${OPERATIONS_VIRTUAL_NETWORK} \
  --subnet deployment-subnet \
  --image ${REGISTRY_NAME}/ops:latest \
  --registry-password ${TF_VAR_operator_client_secret} \
  --registry-username ${TF_VAR_operator_client_id} \
  --memory 4 \
  --cpu 4 \
  --secure-environment-variables "OPS_RESOURCE_GROUP=$TF_VAR_resource_group_name" "OPS_STORAGE_ACCOUNT=$TF_VAR_storage_account_name" "SUBSCRIPTION_ID=$TF_VAR_operator_subscription_id" "SP_CLIENT_ID=$TF_VAR_operator_client_id" "SP_CLIENT_SECRET=$TF_VAR_operator_client_secret" "TENANT_ID=$TF_VAR_operator_tenant_id" "OPS_REGISTRY=$REGISTRY_NAME" "NAMESPACE=$1" "LOGGING_WORKSPACE_ID=$LOGGING_WORKSPACE_ID" "LOGGING_WORKSPACE_RESOURCE_ID=$LOGGING_WORKSPACE_RESOURCE_ID" \
  --command-line "tail -f /dev/null" \
  --log-analytics-workspace $LOGGING_WORKSPACE_ID \
  --restart-policy Never

echo "==============REMEMBER==============="

echo "You must put these files in the config container: \n\t- app.tfvars.json\n\t- atatdev.pem\n\t- ccpo_users.yml"
