#! /bin/bash
set -x
set -e

# How do you find these GUIDs?
#
# Coutesy of Jeff Deville, you can watch your `Network` tab for whichever
# browser's developer tools you're using. There will be a PATCH request.
# The `resourceAppId` will be the `--api` field. The `resourceAccess` ids
# wil be he `--api-permissions values`.
sp=$(az ad sp create-for-rbac)
appId=$(echo $sp | jq .appId | tr -d '"')
subscription_id=$(az account show --query id --output tsv)
objectId=$(az ad sp show --id $appId --query "objectId" --output tsv)
AzureADGraphID=$(az ad sp show --id 00000002-0000-0000-c000-000000000000 --query "objectId" --output tsv)
MSGraphID=$(az ad sp show --id 00000003-0000-0000-c000-000000000000 --query "objectId" --output tsv)
az role assignment create --assignee $appId --role "User Access Administrator" --subscription $subscription_id

# Azure Active Directory
# az ad app permission add --id $appId \
  # --api 00000002-0000-0000-c000-000000000000 \
  # --api-permissions 78c8a3c8-a07e-4b9e-af1b-b5ccab50a175=Scope
  # --api-permissions 78c8a3c8-a07e-4b9e-af1b-b5ccab50a175=Scope



## Application Application.ReadWrite.All
az rest --method POST \
        --uri https://graph.microsoft.com/v1.0/servicePrincipals/$objectId/appRoleAssignments \
        --body "{
          'principalId': '$objectId',
          'resourceId': '$AzureADGraphID',
          'appRoleId': '1cda74f2-2616-4834-b122-5cb1b07f8a59'
        }"
az rest --method POST \
        --uri https://graph.microsoft.com/v1.0/servicePrincipals/$objectId/appRoleAssignments \
        --body "{
          'principalId': '$objectId',
          'resourceId': '$AzureADGraphID',
          'appRoleId': '824c81eb-e3f8-4ee6-8f6d-de7f50d565b7'
        }"
az rest --method POST \
        --uri https://graph.microsoft.com/v1.0/servicePrincipals/$objectId/appRoleAssignments \
        --body "{
          'principalId': '$objectId',
          'resourceId': '$AzureADGraphID',
          'appRoleId': '78c8a3c8-a07e-4b9e-af1b-b5ccab50a175'
        }"
# az ad app permission add --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions 1cda74f2-2616-4834-b122-5cb1b07f8a59=Role
## Application Application.ReadWrite.OwnedBy
# az ad app permission add --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions 824c81eb-e3f8-4ee6-8f6d-de7f50d565b7=Role
# Delegated Directory.ReadWrite.All
### az ad app permission add --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions 78c8a3c8-a07e-4b9e-af1b-b5ccab50a175=Scope

## Directory.AccessAsUser.All
### az ad app permission add --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions a42657d6-7f20-40e3-b6f0-cee03008a62a=Scope
# TODO: it says: `az ad app permission grant --id $appId --api 00000002-0000-0000-c000-000000000000` is needed to make the change effective

# Application Directory.ReadWrite.All
# az ad app permission add --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions 78c8a3c8-a07e-4b9e-af1b-b5ccab50a175=Role
## Delegated User.Read
### az ad app permission grant --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions 311a71cc-e848-46a1-bdf8-97ff7156d8e6=Scope
## Delegated User.Read.All
### az ad app permission grant --id $appId --api 00000002-0000-0000-c000-000000000000 --api-permissions c582532d-9d9e-43bd-a97c-2667a28ce295=Scope

## Azure Key Vault
# Delegated user_impersonation


### az ad app permission add --id $appId --api cfa8b339-82a2-471a-a3c9-0fc0be7a4093 --api-permissions f53da476-18e3-4152-8e01-aec403e6edc0=Scope

# Azure Storage

## Delegated user_impersonation
  # --api-permissions 03e0da56-190b-40ad-a80c-ea378c433f7f=Scope
### az ad app permission add --id $appId --api e406a681-f3d4-42a8-90b6-c2b029497af1 --api-permissions 03e0da56-190b-40ad-a80c-ea378c433f7f=Scope

# Azure Graph
## Application Application.ReadWrite.All
az rest --method POST \
        --uri https://graph.microsoft.com/v1.0/servicePrincipals/$objectId/appRoleAssignments \
        --body "{
          'principalId': '$objectId',
          'resourceId': '$MSGraphID',
          'appRoleId': '1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9'
        }"
# az ad app permission add --id $appId --api 00000003-0000-0000-c000-000000000000 --api-permissions 1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9=Role

## Delegated
  # --api-permissions bdfbf15f-ee85-4955-8675-146e8e5296b5=Scope
## Delegated Application.ReadWrite.All
### az ad app permission add --id $appId --api 00000003-0000-0000-c000-000000000000 --api-permissions bdfbf15f-ee85-4955-8675-146e8e5296b5=Scope
## Delegated User.Read
### az ad app permission add --id $appId --api 00000003-0000-0000-c000-000000000000 --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope


# Allow user impersonation of itself
  # --api-permissions $self_delegation_id=Scope

# self_delegation_id=$(az ad sp list --filter "appid eq '$appId'" --query "[].oauth2Permissions[].id" -o tsv)
# az ad app permission add --id $appId --api $appId --api-permissions $self_delegation_id=Scope

# Grant all permissions
# az ad app permission admin-consent --id $appId

sleep 10

az ad app permission grant --id $appId \
  --api 00000002-0000-0000-c000-000000000000 \
  --scope "Directory.ReadWrite.All Directory.AccessAsUser.All User.Read User.Read.All"
az ad app permission grant --id $appId \
  --api cfa8b339-82a2-471a-a3c9-0fc0be7a4093 \
  --scope "user_impersonation"
az ad app permission grant --id $appId \
  --api e406a681-f3d4-42a8-90b6-c2b029497af1 \
  --scope "user_impersonation"
az ad app permission grant --id $appId \
  --api 00000003-0000-0000-c000-000000000000 \
  --scope "Application.ReadWrite.All User.Read"
az ad app permission grant --id $appId \
  --api $appId \
  --scope "user_impersonation"


echo $sp | jq '.'
echo $sp  > service_principal.json

sleep 10
