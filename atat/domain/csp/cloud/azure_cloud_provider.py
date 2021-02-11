import json
import time
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from secrets import token_hex, token_urlsafe
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin
from uuid import uuid4

from flask import current_app as app

from atat.utils import sha256_hex

from .cloud_provider_interface import CloudProviderInterface
from .exceptions import (
    AuthenticationException,
    ConnectionException,
    DomainNameException,
    ResourceProvisioningError,
    UnknownServerException,
    UserProvisioningException,
)
from .models import (
    AdminRoleDefinitionCSPPayload,
    AdminRoleDefinitionCSPResult,
    ApplicationCSPPayload,
    ApplicationCSPResult,
    BillingInstructionCSPPayload,
    BillingInstructionCSPResult,
    BillingOwnerCSPPayload,
    BillingOwnerCSPResult,
    BillingProfileCreationCSPPayload,
    BillingProfileCreationCSPResult,
    BillingProfileTenantAccessCSPPayload,
    BillingProfileTenantAccessCSPResult,
    BillingProfileVerificationCSPPayload,
    BillingProfileVerificationCSPResult,
    CostManagementQueryCSPPayload,
    CostManagementQueryCSPResult,
    EnvironmentCSPPayload,
    EnvironmentCSPResult,
    InitialMgmtGroupCSPPayload,
    InitialMgmtGroupCSPResult,
    InitialMgmtGroupVerificationCSPPayload,
    InitialMgmtGroupVerificationCSPResult,
    KeyVaultCredentials,
    PoliciesCSPPayload,
    PoliciesCSPResult,
    PrincipalAdminRoleCSPPayload,
    PrincipalAdminRoleCSPResult,
    PrincipalAppGraphApiPermissionsCSPPayload,
    PrincipalAppGraphApiPermissionsCSPResult,
    ProductPurchaseCSPPayload,
    ProductPurchaseCSPResult,
    ProductPurchaseVerificationCSPPayload,
    ProductPurchaseVerificationCSPResult,
    RoleAssignmentPayload,
    ServicePrincipalTokenPayload,
    SubscriptionCreationCSPPayload,
    SubscriptionCreationCSPResult,
    TaskOrderBillingCreationCSPPayload,
    TaskOrderBillingCreationCSPResult,
    TaskOrderBillingVerificationCSPPayload,
    TaskOrderBillingVerificationCSPResult,
    TenantAdminCredentialResetCSPPayload,
    TenantAdminCredentialResetCSPResult,
    TenantAdminOwnershipCSPPayload,
    TenantAdminOwnershipCSPResult,
    TenantCSPPayload,
    TenantCSPResult,
    TenantPrincipalAppCSPPayload,
    TenantPrincipalAppCSPResult,
    TenantPrincipalCredentialCSPPayload,
    TenantPrincipalCredentialCSPResult,
    TenantPrincipalCSPPayload,
    TenantPrincipalCSPResult,
    TenantPrincipalOwnershipCSPPayload,
    TenantPrincipalOwnershipCSPResult,
    UserCSPPayload,
    UserCSPResult,
    UserPrincipalTokenPayload,
    UserRoleCSPPayload,
    UserRoleCSPResult,
    class_to_stage,
)
from .policy import AzurePolicyManager
from .utils import (
    OFFICE_365_DOMAIN,
    create_active_directory_user,
    get_principal_auth_token,
    make_auth_header,
)

# This needs to be a fully pathed role definition identifier, not just a UUID
# TODO: Extract these from sdk msrestazure.azure_cloud import AZURE_PUBLIC_CLOUD
AZURE_SKU_ID = "0001"  # probably a static sku specific to ATAT/JEDI
REMOTE_ROOT_ROLE_DEF_ID = "/providers/Microsoft.Authorization/roleDefinitions/00000000-0000-4000-8000-000000000000"

# This identifier is the application id of the Graph API. Azure automatically
# creates a service principal for this application in each tenant. You can find
# this application in the portal by going to "Enterprise Applications",
# setting the "Application Type" to "all" and searching for "Microsoft Graph".
GRAPH_API_APPLICATION_ID = "00000003-0000-0000-c000-000000000000"

# https://docs.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#user-access-administrator
USER_ACCESS_ADMIN_ROLE_DEFINITION_ID = "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"

DEFAULT_POLICY_SET_DEFINITION_NAME = "Default JEDI Policy Set"

DEFAULT_SCOPE_SUFFIX = "/.default"


def log_and_raise_exceptions(func):
    """Wraps Azure cloud provider API calls to catch `requests` exceptions,
    log them, and re-raise them as our CSP exceptions.

    The cloud parameter below represents an AzureCloudProvider class instance,
    i.e. `self`, since this decorator is applied to class methods.
    """

    @wraps(func)
    def wrapped_func(cloud, *args, **kwargs):
        try:
            return func(cloud, *args, **kwargs)

        except cloud.sdk.requests.exceptions.ConnectionError:
            message = f"Connection Error calling {func.__name__}"
            app.logger.error(message, exc_info=1)
            raise ConnectionException(message)

        except cloud.sdk.requests.exceptions.Timeout:
            message = f"Timeout Error calling {func.__name__}"
            app.logger.error(message, exc_info=1)
            raise ConnectionException(message)

        except cloud.sdk.requests.exceptions.HTTPError as exc:
            exc_string = str(exc)
            status_code = exc_string[:3]
            message = f"error calling {func.__name__}"

            log_format = "%s %s"
            log_values = [status_code, message]

            try:
                response_body = exc.response.json()
                if response_body:
                    log_format += "\n\nResponse Body:\n%s"
                    log_values.append(json.dumps(response_body))
            # No response or body is not parsable to JSON
            except (AttributeError, json.decoder.JSONDecodeError):
                pass

            app.logger.error(
                log_format, *log_values, exc_info=1,
            )
            raise UnknownServerException(
                status_code, f"{message.capitalize()}. {exc_string}"
            )

    return wrapped_func


class AzureSDKProvider(object):
    def __init__(self):
        import requests
        from msrestazure.azure_cloud import (  # TODO: choose cloud type from config
            AZURE_PUBLIC_CLOUD,
        )

        self.cloud = AZURE_PUBLIC_CLOUD
        self.requests = requests


class AsyncOperationStatus(Enum):
    """https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations"""

    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELED = "Canceled"
    IN_PROGRESS = "InProgress"


class AzureCloudProvider(CloudProviderInterface):
    def __init__(self, config, azure_sdk_provider=None):
        self.config = config

        self.client_id = config["AZURE_CLIENT_ID"]
        self.secret_key = config["AZURE_SECRET_KEY"]
        self.root_tenant_id = config["AZURE_TENANT_ID"]
        self.vault_url = config["AZURE_VAULT_URL"]
        self.powershell_client_id = config["AZURE_POWERSHELL_CLIENT_ID"]
        self.graph_resource = config["AZURE_GRAPH_RESOURCE"]
        self.graph_scope = config["AZURE_GRAPH_RESOURCE"] + DEFAULT_SCOPE_SUFFIX
        self.default_aadp_qty = config["AZURE_AADP_QTY"]
        self.roles = {
            "owner": config["AZURE_ROLE_DEF_ID_OWNER"],
            "contributor": config["AZURE_ROLE_DEF_ID_CONTRIBUTOR"],
            "billing": config["AZURE_ROLE_DEF_ID_BILLING_READER"],
        }

        if azure_sdk_provider is None:
            self.sdk = AzureSDKProvider()
        else:
            self.sdk = azure_sdk_provider

        self.policy_manager = AzurePolicyManager(config["AZURE_POLICY_LOCATION"])

    @log_and_raise_exceptions
    def _get_keyvault_token(self):
        url = urljoin(
            self.sdk.cloud.endpoints.active_directory,
            f"{self.root_tenant_id}/oauth2/token",
        )
        resource = f"https://{self.sdk.cloud.suffixes.keyvault_dns[1:]}"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.secret_key,
            "resource": resource,
        }
        token_response = self.sdk.requests.get(url, data=payload, timeout=30)
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if token is None:
            message = f"Failed to get token for resource '{resource}' in tenant '{self.root_tenant_id}'"
            app.logger.error(message, exc_info=1)
            raise AuthenticationException(message)
        else:
            return token

    @log_and_raise_exceptions
    def set_secret(self, secret_key, secret_value):
        kv_token = self._get_keyvault_token()
        result = self.sdk.requests.put(
            f"{self.vault_url}secrets/{secret_key}",
            params={"api-version": "7.1"},
            headers=make_auth_header(kv_token),
            timeout=30,
            json={"value": secret_value},
        )

        result.raise_for_status()
        return result.json()

    @log_and_raise_exceptions
    def get_secret(self, secret_key):
        kv_token = self._get_keyvault_token()
        result = self.sdk.requests.get(
            f"{self.vault_url}secrets/{secret_key}",
            params={"api-version": "7.1"},
            headers=make_auth_header(kv_token),
            timeout=30,
        )

        result.raise_for_status()
        result_value = result.json()["value"]
        return result_value

    def create_environment(self, payload: EnvironmentCSPPayload):
        response = self._create_management_group(
            payload.management_group_name,
            payload.display_name,
            payload.tenant_id,
            payload.parent_id,
        )

        return EnvironmentCSPResult(**response)

    @log_and_raise_exceptions
    def create_application(self, payload: ApplicationCSPPayload):
        response = self._create_management_group(
            payload.management_group_name,
            payload.display_name,
            payload.tenant_id,
            payload.parent_id,
        )

        return ApplicationCSPResult(**response)

    def create_initial_mgmt_group(self, payload: InitialMgmtGroupCSPPayload):
        """Creates the initial management group in the Portfolio tenant.

        Every tenant has a "Root Management Group" (RMG), but this RMG isn't
        provisioned by Azure until another management group is created. In this
        step, we provision a management group solely to trigger the creation of
        the RMG. After this step, we create all other management groups for
        applications and environments under the RMG.

        A management group is a collection of subscriptions and management
        groups to which "governance conditions" can be applied. These resources
        can be nested.

        https://docs.microsoft.com/en-us/azure/governance/management-groups/overview
        """
        response = self._create_management_group(
            payload.management_group_name, payload.display_name, payload.tenant_id,
        )

        return InitialMgmtGroupCSPResult(**response)

    @log_and_raise_exceptions
    def create_initial_mgmt_group_verification(
        self, payload: InitialMgmtGroupVerificationCSPPayload
    ) -> InitialMgmtGroupVerificationCSPResult:
        """Verify the creation of the root management group.

        A management group is a collection of subscriptions and management
        groups to which "governance conditions" can be applied. These resources
        can be nested.

        https://docs.microsoft.com/en-us/azure/governance/management-groups/overview
        """

        with self._get_elevated_access_token(
            payload.tenant_id, payload.user_object_id
        ) as elevated_token:
            url = urljoin(
                self.sdk.cloud.endpoints.resource_manager,
                f"providers/Microsoft.Management/managementGroups/{payload.management_group_name}",
            )
            response = self.sdk.requests.get(
                url,
                headers=make_auth_header(elevated_token),
                params={"api-version": "2020-02-01"},
            )
            response.raise_for_status()
            return InitialMgmtGroupVerificationCSPResult(**response.json())

    @log_and_raise_exceptions
    def _create_management_group(
        self, management_group_id, display_name, tenant_id, parent_id=None,
    ):
        """
        Create a new Azure management group.

        https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/createorupdate
        Args:
            management_group_id: a simple ID for the management group, like a GUID (i.e., not fully qualified)
            display_name: a display name for the management group
            tenant_id: the ID for the Azure Active Directory tenant to create the management group in
            parent_id: (optional) the ID of the parent for the management group
        Returns:
            ManagementGroup: https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/createorupdate#managementgroup
            or
            AzureAsyncOperationResults: https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/createorupdate#azureasyncoperationresults
        """
        sp_token = self._get_tenant_principal_token(tenant_id)
        session = self.sdk.requests.Session()
        session.headers = make_auth_header(sp_token)
        request_body = {"properties": {"displayName": display_name}}

        if parent_id:
            request_body["properties"]["parent"] = {"id": parent_id}
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Management/managementGroups/{management_group_id}",
        )
        response = session.put(
            url, params={"api-version": "2020-02-01"}, json=request_body,
        )
        response.raise_for_status()

        if response.status_code == 202:
            status_url = response.headers["Azure-AsyncOperation"]
            result_url = response.headers["Location"]
            resp = self._poll_management_group_creation_job(
                status_url, result_url, session
            )
        else:
            resp = response.json()

        if parent_id:
            # This should not be necessary, but Azure is currently not
            # respecting the specified parent in the request body of the
            # initial call, so we update it here.
            self._force_apply_mgmt_grp_parent(session, parent_id, management_group_id)

        return resp

    @log_and_raise_exceptions
    def _force_apply_mgmt_grp_parent(self, session, parent_id, management_group_id):
        """
        Update an existing management group to specify its parent.

        https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/update
        Args:
            session: a requests session object
            parent_id: the ID of the parent for the management group
            management_group_id: a simple ID for the management group, like a GUID (i.e., not fully qualified)
        Returns:
            True
        """
        request_body = {"parentId": parent_id}
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Management/managementGroups/{management_group_id}",
        )
        response = session.patch(
            url, params={"api-version": "2020-02-01"}, json=request_body,
        )
        response.raise_for_status()

        return True

    @log_and_raise_exceptions
    def _poll_management_group_creation_job(
        self, status_url: str, result_url: str, session
    ) -> Dict:
        """Polls the management group creation job until it is resolved and
        returns the result.

        https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations

        Args:
            status_url: The url to check for job status, provided by the
                Azure-AsyncOperation response header after creating the
                management group.
            result_url: The url to check for job completion, provided by the
                Locataion response header after creating the
                management group.
            session: a requests session populated with a service principal
                bearer token.
        Returns:
            A dictionary of details of the created management group

        Raises:
            ResourceProvisioningError: Something went wrong when trying to
                create the management group
            RequestException: Something went wrong when trying to make the request
        """

        while True:
            response = session.get(status_url)
            response.raise_for_status()
            response_json = response.json()
            status = response_json["status"]
            if status == AsyncOperationStatus.SUCCEEDED.value:
                resp = session.get(result_url)
                resp.raise_for_status()
                return resp.json()
            elif status in (
                AsyncOperationStatus.FAILED.value,
                AsyncOperationStatus.CANCELED.value,
            ):
                error_message = f"{response_json['error']['message']}\nError code: {response_json['error']['code']}"
                raise ResourceProvisioningError("management group", f"{error_message}")
            else:
                time.sleep(int(response.headers.get("Retry-After", 10)))

    @log_and_raise_exceptions
    def _create_policy_definition(self, session, root_management_group_name, policy):
        create_policy_definition_uri = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Management/managementGroups/{root_management_group_name}/providers/Microsoft.Authorization/policyDefinitions/{policy.definition['properties']['displayName']}",
        )
        body = policy.definition

        result = session.put(
            create_policy_definition_uri,
            params={"api-version": "2019-09-01"},
            json=body,
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code == 201:
            return result.json()

    @log_and_raise_exceptions
    def _create_policy_set(
        self,
        session,
        root_management_group_name,
        policy_set_definition_name,
        definition_references,
    ):
        create_policy_set_uri = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Management/managementGroups/{root_management_group_name}/providers/Microsoft.Authorization/policySetDefinitions/{policy_set_definition_name}",
        )
        body = {
            "properties": {
                "displayName": policy_set_definition_name,
                "policyDefinitions": definition_references,
                "policyType": "Custom",
            }
        }

        result = session.put(
            create_policy_set_uri,
            params={"api-version": "2019-09-01"},
            json=body,
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code in [200, 201]:
            return result.json()

    @log_and_raise_exceptions
    def _create_policy_set_assignment(
        self, session, root_management_group_name, policy_set_definition
    ):
        create_policy_assignment_uri = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Management/managementGroups/{root_management_group_name}/providers/Microsoft.Authorization/policyAssignments/{policy_set_definition['properties']['displayName']}",
        )
        body = {
            "properties": {
                "displayName": policy_set_definition["properties"]["displayName"],
                "policyDefinitionId": policy_set_definition["id"],
            }
        }

        result = session.put(
            create_policy_assignment_uri,
            params={"api-version": "2019-09-01"},
            json=body,
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code == 201:
            return result.json()

    def create_policies(self, payload: PoliciesCSPPayload):
        """
        Creates and applies the default JEDI Policy Set to a portfolio's root management group.

        The underlying API calls seem to be idempotent, despite the fact that most of them repeatedly
        return 201. The _create_policy_set API call is the one exception. It returns 201 on initial
        creation, and then 200 thereafter
        """

        sp_token = self._get_tenant_principal_token(payload.tenant_id)

        policy_session = self.sdk.requests.Session()
        headers = make_auth_header(sp_token)
        policy_session.headers.update(headers)
        definition_references = []
        for policy in self.policy_manager.portfolio_definitions:
            definition = self._create_policy_definition(
                policy_session, payload.root_management_group_name, policy,
            )
            definition_references.append(
                {
                    "policyDefinitionId": definition["id"],
                    "policyDefinitionReferenceId": definition["properties"][
                        "displayName"
                    ],
                    "parameters": policy.parameters,
                }
            )
        policy_set_definition = self._create_policy_set(
            policy_session,
            payload.root_management_group_name,
            DEFAULT_POLICY_SET_DEFINITION_NAME,
            definition_references,
        )
        assign_policy_set = self._create_policy_set_assignment(
            policy_session, payload.root_management_group_name, policy_set_definition
        )
        return PoliciesCSPResult(**assign_policy_set)

    @log_and_raise_exceptions
    def disable_user(self, tenant_id, role_assignment_cloud_id):
        sp_token = self._get_tenant_principal_token(tenant_id)

        # TODO: Normalize this elsewhere in the app so that we can always
        # expect role_assignment_cloud_id to be a UUID
        prefix = "providers/Microsoft.Authorization/roleAssignments/"
        (scope, prefix, assignment_uuid) = role_assignment_cloud_id.rpartition(prefix)
        if not scope:
            scope = f"providers/Microsoft.Management/managementGroups/{tenant_id}/"
        role_assignment_id = scope + prefix + assignment_uuid

        return self._remove_role_assignment(sp_token, role_assignment_id)

    @log_and_raise_exceptions
    def validate_domain_name(self, name):
        url = urljoin(
            self.sdk.cloud.endpoints.active_directory,
            f"{name}.onmicrosoft.com/.well-known/openid-configuration",
        )
        response = self.sdk.requests.get(url, timeout=30,)
        response.raise_for_status()
        # If an existing tenant with name cannot be found, 'error' will be in the response
        return "error" in response.json()

    def generate_valid_domain_name(self, name, suffix="", max_tries=6):
        if max_tries > 0:
            domain_name = name + suffix
            if self.validate_domain_name(domain_name):
                return domain_name
            else:
                suffix = token_hex(3)
                return self.generate_valid_domain_name(name, suffix, max_tries - 1)
        else:
            raise DomainNameException(name)

    @log_and_raise_exceptions
    def create_tenant(self, payload: TenantCSPPayload):
        sp_token = self._get_root_provisioning_token()

        payload.password = token_urlsafe(16)
        payload.domain_name = self.generate_valid_domain_name(payload.domain_name)
        create_tenant_body = payload.dict(by_alias=True)

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            "providers/Microsoft.SignUp/createTenant",
        )
        result = self.sdk.requests.post(
            url,
            params={"api-version": "2020-01-01-preview"},
            json=create_tenant_body,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()

        result_dict = result.json()
        tenant_id = result_dict.get("tenantId")
        tenant_admin_username = (
            f"{payload.user_id}@{payload.domain_name}.{OFFICE_365_DOMAIN}"
        )
        self.create_tenant_creds(
            tenant_id,
            KeyVaultCredentials(
                root_tenant_id=self.root_tenant_id,
                root_sp_client_id=self.client_id,
                root_sp_key=self.secret_key,
                tenant_id=tenant_id,
                tenant_admin_username=tenant_admin_username,
                tenant_admin_password=payload.password,
            ),
        )

        return TenantCSPResult(domain_name=payload.domain_name, **result_dict)

    @log_and_raise_exceptions
    def create_billing_profile_creation(
        self, payload: BillingProfileCreationCSPPayload
    ):
        """Create a billing profile which specifies which products are included
            in an invoice, and how the invoice is paid for.

            Billing profiles include:
            - Payment methods
            - Contact info
            - Permissions

            https://docs.microsoft.com/en-us/microsoft-store/billing-profile
            """
        sp_token = self._get_root_provisioning_token()

        create_billing_account_body = payload.dict(by_alias=True)
        billing_account_create_url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles",
        )
        result = self.sdk.requests.post(
            billing_account_create_url,
            params={"api-version": "2019-10-01-preview"},
            json=create_billing_account_body,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code == 202:
            # 202 has location/retry after headers
            return BillingProfileCreationCSPResult(**result.headers)
        elif result.status_code == 200:
            # NB: Swagger docs imply call can sometimes resolve immediately
            return BillingProfileVerificationCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_billing_profile_verification(
        self, payload: BillingProfileVerificationCSPPayload
    ):
        """Verify that a billing profile has been created.

            A billing profile specifies which products are included in an invoice,
            and how the invoice is paid for. They include:
            - Payment methods
            - Contact info
            - Permissions

            https://docs.microsoft.com/en-us/microsoft-store/billing-profile
            """
        sp_token = self._get_root_provisioning_token()

        result = self.sdk.requests.get(
            payload.billing_profile_verify_url,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()
        return self._handle_async_operation_response(
            result,
            BillingProfileCreationCSPResult,
            BillingProfileVerificationCSPResult,
        )

    @log_and_raise_exceptions
    def create_billing_profile_tenant_access(
        self, payload: BillingProfileTenantAccessCSPPayload
    ):
        sp_token = self._get_root_provisioning_token()
        request_body = {
            "properties": {
                "principalTenantId": payload.tenant_id,  # from tenant creation
                "principalId": payload.user_object_id,  # from tenant creation
                "roleDefinitionId": f"/providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}/billingRoleDefinitions/40000000-aaaa-bbbb-cccc-100000000000",
            }
        }

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}/createBillingRoleAssignment",
        )
        result = self.sdk.requests.post(
            url,
            headers=make_auth_header(sp_token),
            params={"api-version": "2019-10-01-preview"},
            json=request_body,
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code == 201:
            return BillingProfileTenantAccessCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_task_order_billing_creation(
        self, payload: TaskOrderBillingCreationCSPPayload
    ):
        sp_token = self._get_root_provisioning_token()
        request_body = [
            {
                "op": "replace",
                "path": "/enabledAzurePlans",
                "value": [{"skuId": AZURE_SKU_ID}],
            }
        ]

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}",
        )

        result = self.sdk.requests.patch(
            url,
            headers=make_auth_header(sp_token),
            params={"api-version": "2019-10-01-preview"},
            json=request_body,
            timeout=30,
        )
        result.raise_for_status()

        if result.status_code == 202:
            # 202 has location/retry after headers
            return TaskOrderBillingCreationCSPResult(**result.headers)
        elif result.status_code == 200:
            return TaskOrderBillingVerificationCSPResult(**result.json())

    def _handle_async_operation_response(
        self, response, creation_response_model, verification_response_model
    ):
        """Handle the response of an Async operation
        https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations

        Args:
            response (requests.Response): a requests response object
            creation_response_model (pydantic.BaseModel): the model to create and
                return if the operation is still in progress
            verification_response_model (pydantic.BaseModel): the model to
                create and return if the operation succeeds

        Raises:
            ResourceProvisioningError: The operation didn't complete successfully

        Returns:
            pydantic.BaseModel: the creation_response_mode or verification_response_model
        """
        response_json = response.json()
        if response.status_code == 202:
            return creation_response_model(**response.headers, reset_stage=True)
        elif response.status_code == 200:
            status = response_json["status"]
            if status == AsyncOperationStatus.SUCCEEDED.value:
                return verification_response_model(**response_json)
            elif status in (
                AsyncOperationStatus.FAILED.value,
                AsyncOperationStatus.CANCELED.value,
            ):
                provisioning_stage = class_to_stage(verification_response_model)
                error_message = f"{response_json['error']['message']}\nError code: {response_json['error']['code']}"
                raise ResourceProvisioningError(provisioning_stage, f"{error_message}")
            else:
                return creation_response_model(**response.headers, reset_stage=True)

    @log_and_raise_exceptions
    def create_task_order_billing_verification(
        self, payload: TaskOrderBillingVerificationCSPPayload
    ):
        sp_token = self._get_root_provisioning_token()

        result = self.sdk.requests.get(
            payload.task_order_billing_verify_url,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()
        return self._handle_async_operation_response(
            result,
            TaskOrderBillingCreationCSPResult,
            TaskOrderBillingVerificationCSPResult,
        )

    @log_and_raise_exceptions
    def create_billing_instruction(self, payload: BillingInstructionCSPPayload):
        sp_token = self._get_root_provisioning_token()

        request_body = {
            "properties": {
                "amount": payload.initial_clin_amount,
                "startDate": payload.initial_clin_start_date,
                "endDate": payload.initial_clin_end_date,
            }
        }

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}/instructions/{payload.initial_task_order_id}:CLIN00{payload.initial_clin_type}",
        )

        result = self.sdk.requests.put(
            url,
            headers=make_auth_header(sp_token),
            params={"api-version": "2019-10-01-preview"},
            json=request_body,
            timeout=30,
        )
        result.raise_for_status()
        return BillingInstructionCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_subscription(self, payload: SubscriptionCreationCSPPayload, token=None):
        if token is None:
            token = self._get_tenant_principal_token(payload.tenant_id)

        request_body = {
            "displayName": payload.display_name,
            "skuId": AZURE_SKU_ID,
            "managementGroupId": payload.parent_group_id,
        }

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}/invoiceSections/{payload.invoice_section_name}/providers/Microsoft.Subscription/createSubscription",
        )
        result = self.sdk.requests.post(
            url,
            headers=make_auth_header(token),
            params={"api-version": "2019-10-01-preview"},
            json=request_body,
            timeout=30,
        )
        result.raise_for_status()
        if result.status_code in [200, 202]:
            # 202 has location/retry after headers
            return SubscriptionCreationCSPResult(**result.headers, **result.json())

    @log_and_raise_exceptions
    def create_product_purchase(self, payload: ProductPurchaseCSPPayload):
        sp_token = self._get_root_provisioning_token()

        create_product_purchase_body = {
            "type": "AADPremium",
            "sku": "AADP1",
            "productProperties": {"beneficiaryTenantId": payload.tenant_id,},
            "quantity": self.default_aadp_qty,
        }

        product_purchase_url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"providers/Microsoft.Billing/billingAccounts/{payload.billing_account_name}/billingProfiles/{payload.billing_profile_name}/purchaseProduct",
        )

        result = self.sdk.requests.post(
            product_purchase_url,
            params={"api-version": "2019-10-01-preview"},
            json=create_product_purchase_body,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()

        if result.status_code == 202:
            # 202 has location/retry after headers
            return ProductPurchaseCSPResult(**result.headers)
        elif result.status_code == 200:
            # NB: Swagger docs imply call can sometimes resolve immediately
            return ProductPurchaseVerificationCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_product_purchase_verification(
        self, payload: ProductPurchaseVerificationCSPPayload
    ):
        sp_token = self._get_root_provisioning_token()

        result = self.sdk.requests.get(
            payload.product_purchase_verify_url,
            headers=make_auth_header(sp_token),
            timeout=30,
        )
        result.raise_for_status()
        return self._handle_async_operation_response(
            result, ProductPurchaseCSPResult, ProductPurchaseVerificationCSPResult,
        )

    def create_tenant_admin_credential_reset(
        self, payload: TenantAdminCredentialResetCSPPayload
    ):
        """Reset tenant admin password to random value.

        The purpose of this call is to set the password for the tenant admin
        user to a value that is not stored anywhere. You're essentially making
        ATAT "forget" the human admin's login creds when it's done with them.
        """

        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)
        self._update_active_directory_user_password_profile(graph_token, payload)

        return TenantAdminCredentialResetCSPResult()

    @log_and_raise_exceptions
    def _create_role_assignment(self, payload: RoleAssignmentPayload, token):
        """
        https://docs.microsoft.com/en-us/rest/api/authorization/roleassignments/create

        Role assignment definition IDs are assigned at a particular scope
        https://docs.microsoft.com/en-us/azure/role-based-access-control/role-assignments-rest#add-a-role-assignment

        Args:
            payload: a RoleAssignmentPayload model
            token: a token from a user who has elevated access
        Returns:
            Azure RoleAssignment object: https://docs.microsoft.com/en-us/rest/api/authorization/roleassignments/create#roleassignment
        """
        request_body = {
            "properties": {
                "roleDefinitionId": payload.role_definition_id,
                "principalId": payload.principal_id,
            }
        }

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"{payload.role_assignment_scope}/providers/Microsoft.Authorization/roleAssignments/{payload.role_assignment_name}",
        )
        response = self.sdk.requests.put(
            url,
            headers=make_auth_header(token),
            params={"api-version": "2015-07-01"},
            json=request_body,
            timeout=30,
        )
        if (
            response.status_code == 409
            and response.json()["error"]["code"] == "RoleAssignmentExists"
        ):
            app.logger.warning(
                "Tried to create a role assignment that already existed. Role definition name: %s principal id: %s",
                payload.role_definition_name,
                payload.principal_id,
            )
            return self._get_role_assignment_by_definition_and_principal(
                token, payload.role_definition_name, payload.principal_id
            )
        else:
            response.raise_for_status()
            return response.json()

    def _get_role_assignment_by_definition_and_principal(
        self, token, definition_name, principal_id
    ):
        """List the role assignments for a particular principal, then filter by
        defintion id to return a role assignment

        Args:
            definition_name: UUID of a role defintion
            principal_id: UUID for a principal
        """
        role_assignments = self._list_role_assignments(
            token, params={"$filter": f"principalId eq '{principal_id}'"},
        )
        return self._filter_role_assignments(role_assignments, definition_name)

    def create_tenant_admin_ownership(self, payload: TenantAdminOwnershipCSPPayload):
        """Assigns the tenant admin (human user) the Owner role on the root
        management group."""

        role_assignment_payload = RoleAssignmentPayload(
            role_definition_scope=f"/providers/Microsoft.Management/managementGroups/{payload.root_management_group_name}",
            role_definition_name=self.roles["owner"],
            role_assignment_scope=f"/providers/Microsoft.Management/managementGroups/{payload.root_management_group_name}",
            role_assignment_name=str(uuid4()),
            principal_id=payload.user_object_id,
        )
        with self._get_elevated_access_token(
            payload.tenant_id, payload.user_object_id
        ) as elevated_token:
            role_assignment = self._create_role_assignment(
                role_assignment_payload, elevated_token
            )
            return TenantAdminOwnershipCSPResult(**role_assignment)

    @log_and_raise_exceptions
    def create_tenant_principal_ownership(
        self, payload: TenantPrincipalOwnershipCSPPayload
    ):
        """Assigns the the owner role for the service principal over the root management group.

        https://docs.microsoft.com/en-us/rest/api/authorization/roleassignments/create

        Role assignment definition IDs are assigned at a particular scope
        https://docs.microsoft.com/en-us/azure/role-based-access-control/role-assignments-rest#add-a-role-assignment
        """

        role_assignment_payload = RoleAssignmentPayload(
            role_definition_scope=f"/providers/Microsoft.Management/managementGroups/{payload.root_management_group_name}",
            role_definition_name=self.roles["owner"],
            role_assignment_scope=f"/providers/Microsoft.Management/managementGroups/{payload.root_management_group_name}",
            role_assignment_name=str(uuid4()),
            principal_id=payload.principal_id,
        )
        with self._get_elevated_access_token(
            payload.tenant_id, payload.user_object_id
        ) as elevated_token:
            role_assignment = self._create_role_assignment(
                role_assignment_payload, elevated_token
            )
            return TenantPrincipalOwnershipCSPResult(**role_assignment)

    @log_and_raise_exceptions
    def create_tenant_principal_app(self, payload: TenantPrincipalAppCSPPayload):
        """Creates an app registration for a Profile.

        https://docs.microsoft.com/en-us/graph/api/application-post-applications?view=graph-rest-1.0&tabs=http
        """

        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)
        request_body = {"displayName": payload.tenant_principal_app_display_name}

        result = self.sdk.requests.post(
            f"{self.graph_resource}/v1.0/applications",
            json=request_body,
            headers=make_auth_header(graph_token),
            timeout=30,
        )
        result.raise_for_status()
        return TenantPrincipalAppCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_tenant_principal(self, payload: TenantPrincipalCSPPayload):
        """Creates a service principal for a Profile.
        A service principal represents an instance of an application in a
        directory.

        https://docs.microsoft.com/en-us/graph/api/resources/serviceprincipal?view=graph-rest-beta
        https://docs.microsoft.com/en-us/azure/active-directory/develop/app-objects-and-service-principals
        """
        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)
        request_body = {"appId": payload.principal_app_id}

        url = f"{self.graph_resource}/v1.0/servicePrincipals"

        result = self.sdk.requests.post(
            url, json=request_body, headers=make_auth_header(graph_token), timeout=30,
        )
        result.raise_for_status()
        return TenantPrincipalCSPResult(**result.json())

    @log_and_raise_exceptions
    def create_tenant_principal_credential(
        self, payload: TenantPrincipalCredentialCSPPayload, graph_token=None
    ):
        if graph_token is None:
            graph_token = self._get_tenant_admin_token(
                payload.tenant_id, self.graph_scope
            )

        request_body = {
            "passwordCredentials": [{"displayName": "ATAT Generated Password"}]
        }

        response = self.sdk.requests.post(
            f"{self.graph_resource}/v1.0/applications/{payload.principal_app_object_id}/addPassword",
            json=request_body,
            headers=make_auth_header(graph_token),
            timeout=30,
        )
        response.raise_for_status()
        self.update_tenant_creds(
            payload.tenant_id,
            KeyVaultCredentials(
                tenant_id=payload.tenant_id,
                tenant_sp_key=response.json().get("secretText"),
                tenant_sp_client_id=payload.principal_app_id,
            ),
        )
        return TenantPrincipalCredentialCSPResult(
            principal_client_id=payload.principal_app_id,
            principal_creds_established=True,
        )

    @log_and_raise_exceptions
    def create_principal_app_graph_api_permissions(
        self, payload: PrincipalAppGraphApiPermissionsCSPPayload
    ) -> PrincipalAppGraphApiPermissionsCSPResult:
        """Grant the Directory.ReadWrite.All app role assignment to the tenant
        service principal

        https://docs.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignments?view=graph-rest-1.0&tabs=http
        """

        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)
        (
            graph_api_sp_object_id,
            user_invite_app_role_id,
        ) = self._get_graph_sp_and_user_invite_app_role_ids(graph_token)

        request_body = {
            "principalId": payload.principal_id,
            "resourceId": graph_api_sp_object_id,
            "appRoleId": user_invite_app_role_id,
        }

        response = self.sdk.requests.post(
            f"{self.graph_resource}/v1.0/servicePrincipals/{payload.principal_id}/appRoleAssignments",
            json=request_body,
            headers=make_auth_header(graph_token),
        )
        response.raise_for_status()

        return PrincipalAppGraphApiPermissionsCSPResult(**response.json())

    def _extract_service_principal_from_query(self, response):
        """Extract a service principal object from a response

        In `_get_graph_sp_and_user_invite_app_role_ids`, the query parameters
        should make it so that a single service principal object is returned in
        a list. This method returns that single service principal.

        Returns:
            servicePrincipal: https://docs.microsoft.com/en-us/graph/api/resources/serviceprincipal?view=graph-rest-1.0

        Raises:
            ResourceProvisioningError: No service principal present

        """
        service_principal_list = response.json()["value"]
        if not service_principal_list:
            raise ResourceProvisioningError(
                "app role assignment",
                f"No service principals found with id '{GRAPH_API_APPLICATION_ID}'",
            )
        return service_principal_list[0]

    def _extract_app_role_from_service_principal(
        self, service_principal, app_role_value: str
    ):
        """extract an appRole object with a given value from a service principal object

        Args:
            service_principal: a servicePrincipal object https://docs.microsoft.com/en-us/graph/api/resources/serviceprincipal?view=graph-rest-1.0
            app_role_value: the appRole `value` property to find in the list of appRoles

        Returns:
            appRole: https://docs.microsoft.com/en-us/graph/api/resources/approle?view=graph-rest-1.0

        Raises:
            ResourceProvisioningError: No app role found in service principal's appRoles list with the given value
        """
        app_role = next(
            (
                ar
                for ar in service_principal["appRoles"]
                if ar["value"] == app_role_value
            ),
            None,
        )
        if not app_role:
            raise ResourceProvisioningError(
                "app role assignment",
                f"No app role found with value '{app_role_value}'",
            )
        return app_role

    @log_and_raise_exceptions
    def _get_graph_sp_and_user_invite_app_role_ids(
        self, graph_token
    ) -> Tuple[str, str]:
        """Get the service principal object id of the graph api and the app role
        id for the `Directory.ReadWrite.All` app role.

        https://docs.microsoft.com/en-us/graph/api/serviceprincipal-list?view=graph-rest-1.0&tabs=http

        Returns:
            Tuple of the service principal object ID of the Graph API app
            registration and the app role id for "Directory.ReadWrite.All"
        """
        response = self.sdk.requests.get(
            f"{self.graph_resource}/v1.0/servicePrincipals",
            params={
                "$filter": f"servicePrincipalNames/any(name:name eq '{GRAPH_API_APPLICATION_ID}')"
            },
            headers=make_auth_header(graph_token),
        )
        response.raise_for_status()
        graph_service_principal = self._extract_service_principal_from_query(response)
        user_invite_app_role = self._extract_app_role_from_service_principal(
            graph_service_principal, "Directory.ReadWrite.All"
        )
        return graph_service_principal["id"], user_invite_app_role["id"]

    @log_and_raise_exceptions
    def create_admin_role_definition(self, payload: AdminRoleDefinitionCSPPayload):
        """Fetch the UUID for the "Global Administrator" role."""

        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)

        url = f"{self.graph_resource}/beta/roleManagement/directory/roleDefinitions"

        response = self.sdk.requests.get(
            url, headers=make_auth_header(graph_token), timeout=30
        )
        response.raise_for_status()

        result = response.json()
        role_list = result.get("value")
        try:
            admin_role_def_id = next(
                (
                    role.get("id")
                    for role in role_list
                    if role.get("displayName") == "Global Administrator"
                )
            )
            return AdminRoleDefinitionCSPResult(admin_role_def_id=admin_role_def_id)
        except StopIteration:
            raise ResourceProvisioningError(
                "Azure role definition",
                " / Global Administrator role",
            )

    @log_and_raise_exceptions
    def create_principal_admin_role(self, payload: PrincipalAdminRoleCSPPayload):
        """Grant the "Global Administrator" role to the service
        principal (create a role assignment).
        """

        graph_token = self._get_tenant_admin_token(payload.tenant_id, self.graph_scope)
        request_body = {
            "principalId": payload.principal_id,
            "roleDefinitionId": payload.admin_role_def_id,
            "directoryScopeId": "/",
        }

        url = f"{self.graph_resource}/beta/roleManagement/directory/roleAssignments"

        result = self.sdk.requests.post(
            url, headers=make_auth_header(graph_token), json=request_body, timeout=30,
        )
        result.raise_for_status()
        return PrincipalAdminRoleCSPResult(**result.json())

    @log_and_raise_exceptions
    def _get_billing_admin_role_template_id(self, graph_token):
        url = f"{self.graph_resource}/v1.0/directoryRoleTemplates"
        response = self.sdk.requests.get(url, headers=make_auth_header(graph_token))
        response.raise_for_status()
        try:
            role_template = next(
                (
                    role_template
                    for role_template in response.json()["value"]
                    if role_template["displayName"] == "Billing Administrator"
                ),
            )
            return role_template["id"]
        except StopIteration:
            raise UserProvisioningException(
                "Could not find Billing Administrator role template ID."
            )

    @log_and_raise_exceptions
    def _activate_billing_admin_role(self, graph_token, role_template_id):
        request_body = {"roleTemplateId": role_template_id}
        url = f"{self.graph_resource}/v1.0/directoryRoles"
        response = self.sdk.requests.post(
            url, headers=make_auth_header(graph_token), json=request_body
        )
        response.raise_for_status()
        return response.json()["id"]

    def _activate_and_return_billing_admin_role_id(self, graph_token):
        billing_admin_role_template_id = self._get_billing_admin_role_template_id(
            graph_token
        )
        billing_admin_role_id = self._activate_billing_admin_role(
            graph_token, billing_admin_role_template_id
        )
        return billing_admin_role_id

    @log_and_raise_exceptions
    def _get_existing_billing_owner(
        self, token: str, payload: BillingOwnerCSPPayload
    ) -> Optional[UserCSPResult]:
        url = f"{self.graph_resource}/v1.0/users/{payload.user_principal_name}"
        result = self.sdk.requests.get(url, headers=make_auth_header(token))
        if result.status_code == 200:
            return UserCSPResult(**result.json())
        return None

    def create_billing_owner(self, payload: BillingOwnerCSPPayload, graph_token=None):
        """Create a billing account owner, which is a billing role that can
        manage everything for a billing account.

        https://docs.microsoft.com/en-us/azure/cost-management-billing/manage/understand-mca-roles
        """
        if graph_token is None:
            graph_token = self._get_tenant_principal_token(
                payload.tenant_id, scope=self.graph_resource + DEFAULT_SCOPE_SUFFIX
            )

        # Step 1: Retrieve or create an AAD identity for the user
        user_result = self._get_existing_billing_owner(graph_token, payload)
        if not user_result:
            user_result = self._create_active_directory_user(graph_token, payload)

        # Step 2: Set the recovery email
        self._update_active_directory_user_email(graph_token, user_result.id, payload)
        # Step 3: Try and retrieve the billing admin role id. If it isn't found,
        # activate the Billing Admin role and return the id
        # TODO: Find out if we need to check for the Billing Admin role first
        # for provisioning. Will the Billing Admin role be applied by defaut?
        billing_admin_role_id = self._get_billing_owner_role(graph_token)
        if billing_admin_role_id is None:
            billing_admin_role_id = self._activate_and_return_billing_admin_role_id(
                graph_token
            )
        # Step 4: Assign the Billing Administrator role to the new user
        self._assign_billing_owner_role(
            graph_token, billing_admin_role_id, user_result.id
        )

        return BillingOwnerCSPResult(billing_owner_id=user_result.id)

    @log_and_raise_exceptions
    def _assign_billing_owner_role(self, graph_token, billing_admin_role_id, user_id):
        request_body = {
            "roleDefinitionId": billing_admin_role_id,
            "principalId": user_id,
            "directoryScopeId": "/",
        }

        url = f"{self.graph_resource}/beta/roleManagement/directory/roleAssignments"
        result = self.sdk.requests.post(
            url, headers=make_auth_header(graph_token), json=request_body
        )

        error = result.json().get("error")
        if error and "A conflicting object" in error.get("message"):
            return
        result.raise_for_status()

    @log_and_raise_exceptions
    def _get_billing_owner_role(self, graph_token):
        url = f"{self.graph_resource}/v1.0/directoryRoles"
        result = self.sdk.requests.get(url, headers=make_auth_header(graph_token))
        result.raise_for_status()
        result = result.json()
        for role in result["value"]:
            if role["displayName"] == "Billing Administrator":
                return role["id"]

    @log_and_raise_exceptions
    def create_user(self, payload: UserCSPPayload) -> UserCSPResult:
        """Create a user in an Azure Active Directory instance.
        Unlike most of the methods on this interface, this requires
        two API calls: one POST to create the user and one PATCH to
        set the alternate email address. The email address cannot
        be set on the first API call. The email address is
        necessary so that users can do Self-Service Password
        Recovery.

        Arguments:
            payload {UserCSPPayload} -- a payload object with the
            data necessary for both calls

        Returns:
            UserCSPResult -- a result object containing the AAD ID.
        """

        # Request a graph api authorization token

        graph_token = self._get_tenant_principal_token(
            payload.tenant_id, scope=self.graph_resource + DEFAULT_SCOPE_SUFFIX
        )

        # Use the graph api to invite a user

        body = {
            "invitedUserDisplayName": payload.display_name,
            "invitedUserEmailAddress": payload.email,
            "inviteRedirectUrl": "https://portal.azure.com",
            "sendInvitationMessage": True,
            "invitedUserType": "Member",
        }

        url = f"{self.graph_resource}/v1.0/invitations"
        response = self.sdk.requests.post(
            url, json=body, headers=make_auth_header(graph_token)
        )
        response.raise_for_status()

        return UserCSPResult(id=response.json()["invitedUser"]["id"])

    @log_and_raise_exceptions
    def _create_active_directory_user(self, graph_token, payload) -> UserCSPResult:
        result = create_active_directory_user(graph_token, self.graph_resource, payload)
        result.raise_for_status()

        return UserCSPResult(**result.json())

    @log_and_raise_exceptions
    def _update_active_directory_user_email(self, graph_token, user_id, payload):
        request_body = {"otherMails": [payload.email]}

        url = f"{self.graph_resource}/v1.0/users/{user_id}"

        result = self.sdk.requests.patch(
            url, headers=make_auth_header(graph_token), json=request_body, timeout=30,
        )
        result.raise_for_status()
        return True

    @log_and_raise_exceptions
    def _update_active_directory_user_password_profile(self, graph_token, payload):
        request_body = {
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "forceChangePasswordNextSignInWithMfa": False,
                "password": payload.new_password or token_urlsafe(16),
            }
        }

        url = f"{self.graph_resource}/v1.0/users/{payload.user_object_id}"

        result = self.sdk.requests.patch(
            url, headers=make_auth_header(graph_token), json=request_body, timeout=30,
        )
        result.raise_for_status()
        return True

    @log_and_raise_exceptions
    def create_user_role(self, payload: UserRoleCSPPayload):
        graph_token = self._get_tenant_principal_token(payload.tenant_id)

        role_guid = self.roles[payload.role]
        role_definition_id = f"{payload.management_group_id}/providers/Microsoft.Authorization/roleDefinitions/{role_guid}"

        request_body = {
            "properties": {
                "roleDefinitionId": role_definition_id,
                "principalId": payload.user_object_id,
            }
        }

        assignment_guid = str(uuid4())

        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"{payload.management_group_id}/providers/Microsoft.Authorization/roleAssignments/{assignment_guid}",
        )

        response = self.sdk.requests.put(
            url,
            headers=make_auth_header(graph_token),
            params={"api-version": "2015-07-01"},
            json=request_body,
        )

        if response.ok:
            return UserRoleCSPResult(**response.json())
        else:
            raise UserProvisioningException(
                f"Failed to create user role assignment: {response.json()}"
            )

    def _get_tenant_admin_token(self, tenant_id, scope):
        creds = self._source_tenant_creds(tenant_id)
        return self._get_user_principal_token_for_scope(
            creds.tenant_admin_username,
            creds.tenant_admin_password,
            creds.tenant_id,
            scope,
        )

    def _get_root_provisioning_token(self):
        creds = self._source_root_creds()
        return self._get_service_principal_token(
            creds.root_tenant_id, creds.root_sp_client_id, creds.root_sp_key
        )

    @log_and_raise_exceptions
    def _get_service_principal_token(
        self, tenant_id, client_id, secret_key, scope=None
    ):
        payload_scope = scope or self.sdk.cloud.endpoints.resource_manager + ".default"
        payload = ServicePrincipalTokenPayload(
            scope=payload_scope, client_id=client_id, client_secret=secret_key,
        )
        token = get_principal_auth_token(tenant_id, payload)
        if token is None:
            message = f"Failed to get service principal token for scope '{payload_scope}' in tenant '{tenant_id}'"
            app.logger.error(message, exc_info=1)
            raise AuthenticationException(message)
        else:
            return token

    @log_and_raise_exceptions
    def _get_user_principal_token_for_scope(self, username, password, tenant_id, scope):
        payload = UserPrincipalTokenPayload(
            client_id=self.powershell_client_id,
            username=username,
            password=password,
            scope=scope,
        )
        token = get_principal_auth_token(tenant_id, payload)
        if token is None:
            message = f"Failed to get user principal token for scope '{scope}' in tenant '{tenant_id}'"
            app.logger.error(message, exc_info=1)
            raise AuthenticationException(message)
        else:
            return token

    @property
    def _root_creds(self):
        return {
            "client_id": self.client_id,
            "secret_key": self.secret_key,
            "root_tenant_id": self.root_tenant_id,
        }

    def _get_tenant_principal_token(self, tenant_id, scope=None):
        creds = self._source_tenant_creds(tenant_id)
        return self._get_service_principal_token(
            creds.tenant_id,
            creds.tenant_sp_client_id,
            creds.tenant_sp_key,
            scope=scope,
        )

    @log_and_raise_exceptions
    def _elevate_tenant_admin_access(self, token):
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            "providers/Microsoft.Authorization/elevateAccess",
        )
        result = self.sdk.requests.post(
            url,
            headers=make_auth_header(token),
            params={"api-version": "2016-07-01"},
            timeout=30,
        )
        result.raise_for_status()
        return token

    def _source_root_creds(self):
        return KeyVaultCredentials(
            root_tenant_id=self._root_creds.get("root_tenant_id"),
            root_sp_client_id=self._root_creds.get("client_id"),
            root_sp_key=self._root_creds.get("secret_key"),
        )

    def create_tenant_creds(
        self, tenant_id, secret: KeyVaultCredentials
    ) -> KeyVaultCredentials:
        hashed = sha256_hex(tenant_id)
        self.set_secret(hashed, json.dumps(secret.dict()))
        return secret

    def update_tenant_creds(
        self, tenant_id, secret: KeyVaultCredentials
    ) -> KeyVaultCredentials:
        hashed = sha256_hex(tenant_id)
        curr_secrets = self._source_tenant_creds(tenant_id)
        updated_secrets = curr_secrets.merge_credentials(secret)
        self.set_secret(hashed, json.dumps(updated_secrets.dict()))
        return updated_secrets

    def _source_tenant_creds(self, tenant_id) -> KeyVaultCredentials:
        hashed = sha256_hex(tenant_id)
        raw_creds = self.get_secret(hashed)
        return KeyVaultCredentials(**json.loads(raw_creds))

    @log_and_raise_exceptions
    def get_reporting_data(self, payload: CostManagementQueryCSPPayload, token=None):
        """
        Queries the Cost Management API for an invoice section's raw reporting data

        We query at the invoiceSection scope. The full scope path is passed in
        with the payload at the `invoice_section_id` key.
        """
        if token is None:
            token = self._get_tenant_principal_token(payload.tenant_id)

        request_body = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {"from": payload.from_date, "to": payload.to_date,},
            "dataset": {
                "granularity": "Monthly",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [{"type": "Dimension", "name": "InvoiceId"}],
            },
        }
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            f"{payload.invoice_section_id}/providers/Microsoft.CostManagement/query",
        )
        result = self.sdk.requests.post(
            url,
            params={"api-version": "2019-11-01"},
            json=request_body,
            headers=make_auth_header(token),
            timeout=30,
        )
        result.raise_for_status()
        return CostManagementQueryCSPResult(**result.json())

    def get_calculator_url(self):
        calc_access_token = self._get_service_principal_token(
            self.root_tenant_id,
            self.config.get("AZURE_CALC_CLIENT_ID"),
            self.config.get("AZURE_CALC_SECRET"),
            scope=self.config.get("AZURE_CALC_RESOURCE"),
        )
        return f"{self.config.get('AZURE_CALC_URL')}?access_token={calc_access_token}"

    @log_and_raise_exceptions
    def _list_role_assignments(self, token, params=None):
        api_version_param = {"api-version": "2015-07-01"}
        if params is None:
            params = api_version_param
        else:
            params.update(api_version_param)
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            "providers/Microsoft.Authorization/roleAssignments",
        )
        response = self.sdk.requests.get(
            url=url, headers=make_auth_header(token), params=params,
        )
        response.raise_for_status()
        return response.json()["value"]

    @log_and_raise_exceptions
    def _list_role_definitions(self, token, params=None):
        api_version_param = {"api-version": "2015-07-01"}
        if params is None:
            params = api_version_param
        else:
            params.update(api_version_param)
        url = urljoin(
            self.sdk.cloud.endpoints.resource_manager,
            "providers/Microsoft.Authorization/roleDefinitions",
        )
        response = self.sdk.requests.get(
            url=url, headers=make_auth_header(token), params=params,
        )
        response.raise_for_status()
        return response.json()["value"]

    @log_and_raise_exceptions
    def _remove_role_assignment(self, token, role_assignment_id):
        """Removes role assignment in a given tenant

        https://docs.microsoft.com/en-us/rest/api/authorization/roleassignments/delete
        """
        response = self.sdk.requests.delete(
            url=urljoin(self.sdk.cloud.endpoints.resource_manager, role_assignment_id),
            params={"api-version": "2015-07-01"},
            headers=make_auth_header(token),
        )
        response.raise_for_status()
        return response.json()

    def _get_role_definition_id(self, token, role_definition_name):
        definitions = self._list_role_definitions(
            token, params={"$filter": f"roleName eq '{role_definition_name}'"}
        )
        return next((d["name"] for d in definitions), None)

    def _filter_role_assignments(self, assignments, role_definition_name):
        """Find a role assignment in a list of role assignments with a given role definition id"""

        for assignment in assignments:
            if assignment["properties"]["roleDefinitionId"].endswith(
                role_definition_name
            ):
                return assignment
        return None

    def _remove_tenant_admin_elevated_access(
        self, tenant_id, tenant_admin_user_object_id, token=None
    ) -> bool:
        """Remove the User Access Administrator role assignment from the tenant admin"""

        if token is None:
            token = self._get_tenant_admin_token(
                tenant_id, self.sdk.cloud.endpoints.resource_manager + "/.default",
            )

        # The User Access Administrator definition id may be a constant, but
        # other documentation describing this process includes listing
        # definitions to find the ID:
        # https://docs.microsoft.com/en-us/azure/role-based-access-control/elevate-access-global-admin#remove-elevated-access-3
        # Here, we try to get the id by listing first, but use the default in
        # case we can't find it
        definition_id = (
            self._get_role_definition_id(
                token, role_definition_name="User Access Administrator"
            )
            or USER_ACCESS_ADMIN_ROLE_DEFINITION_ID
        )

        try:
            assignment = self._get_role_assignment_by_definition_and_principal(
                token, definition_id, tenant_admin_user_object_id
            )
        except UnknownServerException as exc:
            if exc.status_code == "403":
                app.logger.warning(
                    (
                        "Tenant admin of tenant %s unable to list role assignments."
                        "This could indicate that the tenant admin does not have a User"
                        "Access Administrator role assignment."
                    ),
                    tenant_id,
                )
                return True
            else:
                raise exc

        if not assignment:
            app.logger.warning(
                "User Access Administrator role assignment not found for user %s in tenant %s",
                tenant_admin_user_object_id,
                tenant_id,
            )
            return True

        return bool(self._remove_role_assignment(token, assignment["id"]))

    @contextmanager
    def _get_elevated_access_token(self, tenant_id, user_object_id):

        tenant_admin_token = self._get_tenant_admin_token(
            tenant_id, self.sdk.cloud.endpoints.resource_manager + "/.default"
        )
        self._elevate_tenant_admin_access(tenant_admin_token)
        app.logger.info(
            "Assigned User Access Administrator to user %s in tenant %s",
            user_object_id,
            tenant_id,
        )
        elevated_token = None
        try:
            elevated_token = self._get_tenant_admin_token(
                tenant_id, self.sdk.cloud.endpoints.resource_manager + "/.default"
            )
            yield elevated_token
        finally:
            try:
                remove_access_token = elevated_token or tenant_admin_token
                self._remove_tenant_admin_elevated_access(
                    tenant_id, user_object_id, token=remove_access_token
                )
                app.logger.info(
                    "Succssfully removed User Access Administrator assignment from user %s in tenant %s",
                    user_object_id,
                    tenant_id,
                )
            except self.sdk.requests.exceptions.RequestException:
                app.logger.error(
                    "Could not remove User Access Administrator for user %s in tenant %s",
                    user_object_id,
                    tenant_id,
                )
                raise Exception("Error removing elevated access")
