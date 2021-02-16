import contextlib
from operator import itemgetter
from typing import Dict, Union
from uuid import uuid4

from atat.domain.csp.cloud.azure_cloud_provider import AzureCloudProvider
from atat.domain.csp.cloud.mock_cloud_provider import MockCloudProvider
from atat.domain.csp.cloud.models import (
    AdminRoleDefinitionCSPPayload,
    AdminRoleDefinitionCSPResult,
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
    SubscriptionCreationCSPPayload,
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
    UserRoleCSPPayload,
    UserRoleCSPResult,
)


@contextlib.contextmanager
def monkeypatched(object_, name, patch):
    """ Temporarily monkeypatches an object. """

    pre_patched_value = getattr(object_, name)
    setattr(object_, name, patch)
    yield object_
    setattr(object_, name, pre_patched_value)


HYBRID_PREFIX = "Hybrid ::"


class HybridCloudProvider(object):
    def __init__(self, azure: AzureCloudProvider, mock: MockCloudProvider, config):
        self.azure = azure
        self.mock = mock
        self.hybrid_tenant_id = config["AZURE_HYBRID_TENANT_ID"]
        self.domain_name = config["AZURE_HYBRID_TENANT_DOMAIN"]
        self.hybrid_reporting_client_id = config["AZURE_HYBRID_REPORTING_CLIENT_ID"]
        self.hybrid_reporting_secret_key = config["AZURE_HYBRID_REPORTING_SECRET"]

    def create_tenant(self, payload: TenantCSPPayload) -> TenantCSPResult:
        """In this step, we store a tenant ID with a username and password
        provided to the application ahead of time. Normally the tenant is
        created through API calls to Azure, however for the hybrid mock we
        will generate and store a tenant with a simple generated UUID string
        instead.
        """

        # This is the username and password for the primary point of contact
        # for a portfolio. These are normally generated for the tenant, but
        # but here we just inject existing and valid credentials.
        tenant_admin_username = self.azure.config["AZURE_TENANT_ADMIN_USERNAME"]
        tenant_admin_password = self.azure.config["AZURE_TENANT_ADMIN_PASSWORD"]
        user_object_id = self.azure.config["AZURE_USER_OBJECT_ID"]
        mock_tenant_id = str(uuid4())

        # This is our mocked result of what would have been the API call to
        # create a tenant.
        result_dict = {
            "tenant_id": mock_tenant_id,
            "user_id": "HybridCSPIntegrationTestUser",
            "user_object_id": user_object_id,
            "tenant_admin_username": tenant_admin_username,
            "tenant_admin_password": tenant_admin_password,
        }

        # Here we use the tenant id as a KeyVault key to store the primary
        # point of contact credentials.
        self.azure.create_tenant_creds(
            mock_tenant_id,
            KeyVaultCredentials(
                root_tenant_id=self.azure.root_tenant_id,
                root_sp_client_id=self.azure.client_id,
                root_sp_key=self.azure.secret_key,
                tenant_id=self.hybrid_tenant_id,
                tenant_admin_username=tenant_admin_username,
                tenant_admin_password=tenant_admin_password,
            ),
        )

        return TenantCSPResult(domain_name=self.domain_name, **result_dict)

    def create_billing_profile_creation(
        self, payload: BillingProfileCreationCSPPayload
    ) -> Union[BillingProfileCreationCSPResult, BillingProfileVerificationCSPResult]:
        return self.mock.create_billing_profile_creation(payload)

    def create_billing_profile_verification(
        self, payload: BillingProfileVerificationCSPPayload
    ) -> Union[BillingProfileCreationCSPResult, BillingProfileVerificationCSPResult]:
        return self.mock.create_billing_profile_verification(payload)

    def create_billing_profile_tenant_access(
        self, payload: BillingProfileTenantAccessCSPPayload
    ) -> BillingProfileTenantAccessCSPResult:
        return self.mock.create_billing_profile_tenant_access(payload)

    def create_task_order_billing_creation(
        self, payload: TaskOrderBillingCreationCSPPayload
    ) -> Union[
        TaskOrderBillingCreationCSPResult, TaskOrderBillingVerificationCSPResult
    ]:
        return self.mock.create_task_order_billing_creation(payload)

    def create_task_order_billing_verification(
        self, payload: TaskOrderBillingVerificationCSPPayload
    ) -> Union[
        TaskOrderBillingCreationCSPResult, TaskOrderBillingVerificationCSPResult
    ]:
        return self.mock.create_task_order_billing_verification(payload)

    def create_billing_instruction(
        self, payload: BillingInstructionCSPPayload
    ) -> BillingInstructionCSPResult:
        return self.mock.create_billing_instruction(payload)

    def create_product_purchase(
        self, payload: ProductPurchaseCSPPayload
    ) -> Union[ProductPurchaseCSPResult, ProductPurchaseVerificationCSPResult]:
        return self.mock.create_product_purchase(payload)

    def create_product_purchase_verification(
        self, payload: ProductPurchaseVerificationCSPPayload
    ) -> Union[ProductPurchaseCSPResult, ProductPurchaseVerificationCSPResult]:
        return self.mock.create_product_purchase_verification(payload)

    def create_tenant_principal_app(
        self, payload: TenantPrincipalAppCSPPayload
    ) -> TenantPrincipalAppCSPResult:
        payload.tenant_principal_app_display_name = "{} {} :: {}".format(
            HYBRID_PREFIX,
            payload.display_name,
            payload.tenant_principal_app_display_name,
        )
        return self.azure.create_tenant_principal_app(payload)

    def create_tenant_principal(
        self, payload: TenantPrincipalCSPPayload
    ) -> TenantPrincipalCSPResult:
        return self.azure.create_tenant_principal(payload)

    def create_tenant_principal_credential(
        self, payload: TenantPrincipalCredentialCSPPayload
    ) -> TenantPrincipalCredentialCSPResult:
        token = self.azure._get_tenant_admin_token(
            payload.tenant_id, self.azure.graph_resource + "/.default"
        )

        original_update_tenant_creds = self.azure.update_tenant_creds

        def mocked_update_tenant_creds(tenant_id, creds):
            """Necessary to ensure the hybrid tenant id credentials are saved in
            KeyVault at the end of this stage.
            """
            creds.tenant_id = self.hybrid_tenant_id
            original_update_tenant_creds(tenant_id, creds)

        with monkeypatched(
            self.azure, "update_tenant_creds", mocked_update_tenant_creds
        ):
            return self.azure.create_tenant_principal_credential(
                payload, graph_token=token
            )

    def create_admin_role_definition(
        self, payload: AdminRoleDefinitionCSPPayload
    ) -> AdminRoleDefinitionCSPResult:
        return self.azure.create_admin_role_definition(payload)

    def create_principal_app_graph_api_permissions(
        self, payload: PrincipalAppGraphApiPermissionsCSPPayload
    ) -> PrincipalAppGraphApiPermissionsCSPResult:
        return self.azure.create_principal_app_graph_api_permissions(payload)

    def create_principal_admin_role(
        self, payload: PrincipalAdminRoleCSPPayload
    ) -> PrincipalAdminRoleCSPResult:
        return self.azure.create_principal_admin_role(payload)

    def create_initial_mgmt_group(
        self, payload: InitialMgmtGroupCSPPayload
    ) -> InitialMgmtGroupCSPResult:
        """Normally, we create an initial management group just to trigger the 
        creation of the root management group and don't care about the name 
        of this initial management group for the rest of provisioning. Here 
        though, we patch the payload with the csp_data tenant id that was 
        created in `create_tenant`. Now, when cloud models that require a 
        root_management_group_name field access the `tenant_id` in csp data to 
        populate that field, they will use this initial management group / mock 
        tenant id value. This way, each portfolio will get its own management 
        group under the hybrid tenant."""

        payload.display_name = f"{HYBRID_PREFIX} {payload.display_name}"
        payload.management_group_name = payload.tenant_id
        return self.azure.create_initial_mgmt_group(payload)

    def create_initial_mgmt_group_verification(
        self, payload: InitialMgmtGroupVerificationCSPPayload
    ) -> InitialMgmtGroupVerificationCSPResult:
        return self.azure.create_initial_mgmt_group_verification(payload)

    def create_tenant_admin_ownership(
        self, payload: TenantAdminOwnershipCSPPayload
    ) -> TenantAdminOwnershipCSPResult:
        return self.azure.create_tenant_admin_ownership(payload)

    def create_tenant_principal_ownership(
        self, payload: TenantPrincipalOwnershipCSPPayload
    ) -> TenantPrincipalOwnershipCSPResult:
        return self.azure.create_tenant_principal_ownership(payload)

    def create_billing_owner(
        self, payload: BillingOwnerCSPPayload
    ) -> BillingOwnerCSPResult:
        token = self.azure._get_tenant_principal_token(
            payload.tenant_id, scope=self.azure.graph_resource + "/.default"
        )
        payload.tenant_id = self.hybrid_tenant_id
        payload.display_name = f"{HYBRID_PREFIX} {payload.display_name} :: Billing"
        return self.azure.create_billing_owner(payload, graph_token=token)

    def create_tenant_admin_credential_reset(
        self, payload: TenantAdminCredentialResetCSPPayload
    ) -> TenantAdminCredentialResetCSPResult:
        return self.mock.create_tenant_admin_credential_reset(payload)

    def create_policies(self, payload: PoliciesCSPPayload) -> PoliciesCSPResult:
        return self.azure.create_policies(payload)

    def create_application(self, payload):
        payload.display_name = f"{HYBRID_PREFIX} {payload.display_name}"
        return self.azure.create_application(payload)

    def create_environment(
        self, payload: EnvironmentCSPPayload
    ) -> EnvironmentCSPResult:
        payload.display_name = f"{HYBRID_PREFIX} {payload.display_name}"
        return self.azure.create_environment(payload)

    def create_user(self, payload: UserCSPPayload) -> UserCSPResult:
        return self.azure.create_user(payload)

    def create_user_role(self, payload: UserRoleCSPPayload) -> UserRoleCSPResult:
        return self.azure.create_user_role(payload)

    def disable_user(self, tenant_id: str, role_assignment_cloud_id: str) -> Dict:
        return self.azure.disable_user(tenant_id, role_assignment_cloud_id)

    def get_reporting_data(self, payload: CostManagementQueryCSPPayload):
        billing_account_id, billing_profile_id, invoice_section_id = itemgetter(
            "AZURE_BILLING_ACCOUNT_NAME",
            "AZURE_BILLING_PROFILE_ID",
            "AZURE_INVOICE_SECTION_ID",
        )(self.azure.config)

        payload.invoice_section_id = f"/providers/Microsoft.Billing/billingAccounts/{billing_account_id}/billingProfiles/{billing_profile_id}/invoiceSections/{invoice_section_id}"
        payload.tenant_id = self.azure.root_tenant_id

        hybrid_reporting_token = self.azure._get_service_principal_token(
            self.azure.root_tenant_id,
            self.hybrid_reporting_client_id,
            self.hybrid_reporting_secret_key,
        )
        return self.azure.get_reporting_data(payload, token=hybrid_reporting_token)

    def create_subscription(self, payload: SubscriptionCreationCSPPayload):
        # TODO: This will need to be updated to use the azure function. Additionally,
        # the payload display_name will have to be prepended with the hybrid prefix.
        #
        # Example code:
        # payload.display_name = f"{HYBRID_PREFIX} {payload.display_name}"
        # return self.azure.create_subscription(payload)
        return self.mock.create_subscription(payload)
