from uuid import uuid4

import pendulum

from .cloud_provider_interface import CloudProviderInterface
from .exceptions import (
    AuthenticationException,
    AuthorizationException,
    ConnectionException,
    GeneralCSPException,
    UnknownServerException,
    UserProvisioningException,
    UserRemovalException,
)
from .models import (
    AZURE_MGMNT_PATH,
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
    UserRoleCSPPayload,
    UserRoleCSPResult,
)


class MockCloudProvider(CloudProviderInterface):
    # TODO: All of these constants
    AUTHENTICATION_EXCEPTION = AuthenticationException("Authentication failure.")
    AUTHORIZATION_EXCEPTION = AuthorizationException("Not authorized.")
    NETWORK_EXCEPTION = ConnectionException("Network failure.")
    SERVER_EXCEPTION = UnknownServerException(500, "Not our fault.")

    SERVER_FAILURE_PCT = 1
    NETWORK_FAILURE_PCT = 7
    ENV_CREATE_FAILURE_PCT = 12
    ATAT_ADMIN_CREATE_FAILURE_PCT = 12
    UNAUTHORIZED_RATE = 2

    _MOCK_URL = "https://zombo.com"

    def __init__(
        self, config, with_delay=True, with_failure=True, with_authorization=True
    ):
        import random
        from time import sleep

        self._with_delay = with_delay
        self._with_failure = with_failure
        self._with_authorization = with_authorization
        self._sleep = sleep
        self._random = random

    def root_creds(self):
        return self._auth_credentials

    def set_secret(self, secret_key: str, secret_value: str):
        # TODO: Add implementation
        pass

    def get_secret(self, secret_key: str, default=dict()):
        return default

    def create_subscription(self, payload: SubscriptionCreationCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return SubscriptionCreationCSPResult(
            subscription_verify_url=self._MOCK_URL, subscription_retry_after=10
        )

    def create_tenant(self, payload: TenantCSPPayload):
        """
        payload is an instance of TenantCSPPayload data class
        """

        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantCSPResult(
            **{
                "tenant_id": "",
                "user_id": "",
                "user_object_id": "",
                "domain_name": "",
                "tenant_admin_username": "test",
                "tenant_admin_password": "test",
            }
        )

    def create_billing_profile_creation(
        self, payload: BillingProfileCreationCSPPayload
    ):
        # response will be mostly the same as the body, but we only really care about the id
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return BillingProfileCreationCSPResult(
            **dict(
                billing_profile_verify_url=self._MOCK_URL,
                billing_profile_retry_after=10,
            )
        )

    def create_billing_profile_verification(
        self, payload: BillingProfileVerificationCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)
        return BillingProfileVerificationCSPResult(
            **{
                "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB",
                "name": "KQWI-W2SU-BG7-TGB",
                "properties": {
                    "address": {
                        "addressLine1": "123 S Broad Street, Suite 2400",
                        "city": "Philadelphia",
                        "companyName": "Promptworks",
                        "country": "US",
                        "postalCode": "19109",
                        "region": "PA",
                    },
                    "currency": "USD",
                    "displayName": "Test Billing Profile",
                    "enabledAzurePlans": [],
                    "hasReadAccess": True,
                    "invoiceDay": 5,
                    "invoiceEmailOptIn": False,
                    "invoiceSections": [
                        {
                            "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB/invoiceSections/CHCO-BAAR-PJA-TGB",
                            "name": "CHCO-BAAR-PJA-TGB",
                            "properties": {"displayName": "Test Billing Profile"},
                            "type": "Microsoft.Billing/billingAccounts/billingProfiles/invoiceSections",
                        }
                    ],
                },
                "type": "Microsoft.Billing/billingAccounts/billingProfiles",
            }
        )

    def create_billing_profile_tenant_access(self, payload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return BillingProfileTenantAccessCSPResult(
            **{
                "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB/billingRoleAssignments/40000000-aaaa-bbbb-cccc-100000000000_0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d",
                "name": "40000000-aaaa-bbbb-cccc-100000000000_0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d",
                "properties": {
                    "createdOn": "2020-01-14T14:39:26.3342192+00:00",
                    "createdByPrincipalId": "82e2b376-3297-4096-8743-ed65b3be0b03",
                    "principalId": "0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d",
                    "principalTenantId": "60ff9d34-82bf-4f21-b565-308ef0533435",
                    "roleDefinitionId": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB/billingRoleDefinitions/40000000-aaaa-bbbb-cccc-100000000000",
                    "scope": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB",
                },
                "type": "Microsoft.Billing/billingRoleAssignments",
            }
        )

    def create_task_order_billing_creation(
        self, payload: TaskOrderBillingCreationCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TaskOrderBillingCreationCSPResult(
            **{"Location": "https://somelocation", "Retry-After": "10"}
        )

    def create_task_order_billing_verification(
        self, payload: TaskOrderBillingVerificationCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TaskOrderBillingVerificationCSPResult(
            **{
                "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/XC36-GRNZ-BG7-TGB",
                "name": "XC36-GRNZ-BG7-TGB",
                "properties": {
                    "address": {
                        "addressLine1": "123 S Broad Street, Suite 2400",
                        "city": "Philadelphia",
                        "companyName": "Promptworks",
                        "country": "US",
                        "postalCode": "19109",
                        "region": "PA",
                    },
                    "currency": "USD",
                    "displayName": "First Portfolio Billing Profile",
                    "enabledAzurePlans": [
                        {
                            "productId": "DZH318Z0BPS6",
                            "skuId": "0001",
                            "skuDescription": "Microsoft Azure Plan",
                        }
                    ],
                    "hasReadAccess": True,
                    "invoiceDay": 5,
                    "invoiceEmailOptIn": False,
                },
                "type": "Microsoft.Billing/billingAccounts/billingProfiles",
            }
        )

    def create_billing_instruction(self, payload: BillingInstructionCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return BillingInstructionCSPResult(
            **{
                "name": "TO1:CLIN001",
                "properties": {
                    "amount": 1000.0,
                    "endDate": "2020-03-01T00:00:00+00:00",
                    "startDate": "2020-01-01T00:00:00+00:00",
                },
                "type": "Microsoft.Billing/billingAccounts/billingProfiles/billingInstructions",
            }
        )

    def create_initial_mgmt_group(self, payload: InitialMgmtGroupCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return InitialMgmtGroupCSPResult(
            id=f"{AZURE_MGMNT_PATH}{payload.management_group_name}",
            name=payload.management_group_name,
        )

    def create_initial_mgmt_group_verification(
        self, payload: InitialMgmtGroupVerificationCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return InitialMgmtGroupVerificationCSPResult(
            **dict(id=f"{AZURE_MGMNT_PATH}{payload.management_group_name}")
        )

    def create_product_purchase(self, payload: ProductPurchaseCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return ProductPurchaseCSPResult(
            **dict(
                product_purchase_verify_url=self._MOCK_URL,
                product_purchase_retry_after=10,
            )
        )

    def create_product_purchase_verification(
        self, payload: ProductPurchaseVerificationCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return ProductPurchaseVerificationCSPResult(
            **dict(premium_purchase_date="2020-01-30T18:57:05.981Z")
        )

    def create_tenant_admin_ownership(self, payload: TenantAdminOwnershipCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)
        return TenantAdminOwnershipCSPResult(**dict(id="admin_owner_assignment_id"))

    def create_tenant_admin_credential_reset(
        self, payload: TenantAdminCredentialResetCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantAdminCredentialResetCSPResult()

    def create_tenant_principal_ownership(
        self, payload: TenantPrincipalOwnershipCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantPrincipalOwnershipCSPResult(
            **dict(id="principal_owner_assignment_id")
        )

    def create_tenant_principal_app(self, payload: TenantPrincipalAppCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantPrincipalAppCSPResult(
            **dict(appId="principal_app_id", id="principal_app_object_id")
        )

    def create_tenant_principal(self, payload: TenantPrincipalCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantPrincipalCSPResult(**dict(id="principal_id"))

    def create_tenant_principal_credential(
        self, payload: TenantPrincipalCredentialCSPPayload
    ):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return TenantPrincipalCredentialCSPResult(
            **dict(
                principal_client_id="principal_client_id",
                principal_creds_established=True,
            )
        )

    def create_admin_role_definition(self, payload: AdminRoleDefinitionCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return AdminRoleDefinitionCSPResult(
            **dict(admin_role_def_id="admin_role_def_id")
        )

    def create_principal_admin_role(self, payload: PrincipalAdminRoleCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return PrincipalAdminRoleCSPResult(**dict(id="principal_assignment_id"))

    def create_billing_owner(self, payload: BillingOwnerCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return BillingOwnerCSPResult(billing_owner_id="foo")

    def create_or_update_user(self, auth_credentials, user_info, csp_role_id):
        self._authorize(auth_credentials)

        self._delay(1, 5)
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(
            self.ATAT_ADMIN_CREATE_FAILURE_PCT,
            UserProvisioningException(
                user_info.environment.id,
                user_info.application_role.user_id,
                "Could not create user.",
            ),
        )

        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)
        return self._id()

    def disable_user(self, tenant_id, role_assignment_cloud_id):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)

        self._maybe_raise(
            self.ATAT_ADMIN_CREATE_FAILURE_PCT,
            UserRemovalException(tenant_id, "Could not disable user."),
        )

        return self._maybe(12)

    def create_user_role(self, payload: UserRoleCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHENTICATION_EXCEPTION)

        return UserRoleCSPResult(id=f"{AZURE_MGMNT_PATH}{uuid4()}",)

    def get_calculator_url(self):
        return "https://www.rackspace.com/en-us/calculator"

    def get_environment_login_url(self, environment):
        """Returns the login url for a given environment
        """
        return "https://www.mycloud.com/my-env-login"

    def _id(self):
        return uuid4().hex

    def _delay(self, min_secs, max_secs):
        if self._with_delay:
            duration = self._random.randrange(min_secs, max_secs)
            self._sleep(duration)

    def _maybe(self, pct):
        return not self._with_failure or self._random.randrange(0, 100) < pct

    def _maybe_raise(self, pct, exc):
        if self._with_failure and self._maybe(pct):
            raise exc

    @property
    def _auth_credentials(self):
        return {"username": "mock-cloud", "password": "shh"}  # pragma: allowlist secret

    def _authorize(self, credentials):
        self._delay(1, 5)
        if self._with_authorization and credentials != self._auth_credentials:
            raise self.AUTHENTICATION_EXCEPTION

    def create_application(self, payload: ApplicationCSPPayload):
        self._maybe_raise(self.UNAUTHORIZED_RATE, GeneralCSPException)

        return ApplicationCSPResult(
            id=f"{AZURE_MGMNT_PATH}{payload.management_group_name}",
            name=payload.management_group_name,
        )

    def create_environment(self, payload: EnvironmentCSPPayload):
        self._maybe_raise(self.UNAUTHORIZED_RATE, GeneralCSPException)

        return EnvironmentCSPResult(
            id=f"{AZURE_MGMNT_PATH}{payload.management_group_name}",
            name=payload.management_group_name,
        )

    def create_user(self, payload: UserCSPPayload):
        self._maybe_raise(self.UNAUTHORIZED_RATE, GeneralCSPException)

        return UserCSPResult(id=str(uuid4()))

    def get_credentials(self, scope="portfolio", tenant_id=None):
        return self.root_creds()

    def update_tenant_creds(self, tenant_id, secret):
        return secret

    def get_reporting_data(self, payload: CostManagementQueryCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)
        object_id = str(uuid4())

        start_of_month = pendulum.today(tz="UTC").start_of("month").replace(tzinfo=None)
        this_month = start_of_month.to_atom_string()
        last_month = start_of_month.subtract(months=1).to_atom_string()
        two_months_ago = start_of_month.subtract(months=2).to_atom_string()

        properties = {
            "columns": [
                {"name": "PreTaxCost", "type": "Number"},
                {"name": "BillingMonth", "type": "Datetime"},
                {"name": "InvoiceId", "type": "String"},
                {"name": "Currency", "type": "String"},
            ],
            "rows": [
                [1.0, two_months_ago, "", "USD"],
                [500.0, two_months_ago, "e05009w9sf", "USD"],
                [50.0, last_month, "", "USD"],
                [1000.0, last_month, "e0500a4qhw", "USD"],
                [500.0, this_month, "", "USD"],
            ],
        }

        return CostManagementQueryCSPResult(name=object_id, properties=properties)

    def create_policies(self, payload: PoliciesCSPPayload):
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return PoliciesCSPResult(
            policy_assignment_id=f"{AZURE_MGMNT_PATH}{payload.root_management_group_name}/providers/Microsoft.Authorization/policyAssignments/Default JEDI Policy Set",
        )

    def create_principal_app_graph_api_permissions(
        self, payload: PrincipalAppGraphApiPermissionsCSPPayload
    ) -> PrincipalAppGraphApiPermissionsCSPResult:
        self._maybe_raise(self.NETWORK_FAILURE_PCT, self.NETWORK_EXCEPTION)
        self._maybe_raise(self.SERVER_FAILURE_PCT, self.SERVER_EXCEPTION)
        self._maybe_raise(self.UNAUTHORIZED_RATE, self.AUTHORIZATION_EXCEPTION)

        return PrincipalAppGraphApiPermissionsCSPResult()
