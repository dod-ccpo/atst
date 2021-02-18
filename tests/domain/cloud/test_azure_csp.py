import json
from contextlib import contextmanager
from unittest.mock import Mock, call
from uuid import uuid4

import pendulum
import pydantic
import pytest

import atat.domain.csp.cloud.azure_cloud_provider
from atat.domain.csp.cloud import AzureCloudProvider
from atat.domain.csp.cloud.azure_cloud_provider import log_and_raise_exceptions
from atat.domain.csp.cloud.exceptions import (
    AuthenticationException,
    ConnectionException,
    DomainNameException,
    ResourceProvisioningError,
    UnknownServerException,
    UserProvisioningException,
)
from atat.domain.csp.cloud.models import (
    AdminRoleDefinitionCSPPayload,
    AdminRoleDefinitionCSPResult,
    ApplicationCSPPayload,
    ApplicationCSPResult,
    BillingInstructionCSPPayload,
    BillingInstructionCSPResult,
    BillingOwnerCSPPayload,
    BillingProfileCreationCSPPayload,
    BillingProfileCreationCSPResult,
    BillingProfileTenantAccessCSPPayload,
    BillingProfileTenantAccessCSPResult,
    BillingProfileVerificationCSPPayload,
    BillingProfileVerificationCSPResult,
    CostManagementQueryCSPPayload,
    CostManagementQueryCSPResult,
    EnvironmentCSPPayload,
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
    ProductPurchaseCSPPayload,
    ProductPurchaseCSPResult,
    ProductPurchaseVerificationCSPPayload,
    ProductPurchaseVerificationCSPResult,
    SubscriptionCreationCSPPayload,
    SubscriptionCreationCSPResult,
    SubscriptionVerificationCSPPayload,
    SuscriptionVerificationCSPResult,
    TaskOrderBillingCreationCSPPayload,
    TaskOrderBillingCreationCSPResult,
    TaskOrderBillingVerificationCSPPayload,
    TaskOrderBillingVerificationCSPResult,
    TenantAdminCredentialResetCSPPayload,
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
)
from tests.factories import ApplicationFactory, EnvironmentFactory
from tests.mock_azure import (  # pylint: disable=W0611
    AZURE_CONFIG,
    MOCK_ACCESS_TOKEN,
    mock_azure,
)

BILLING_ACCOUNT_NAME = "52865e4c-52e8-5a6c-da6b-c58f0814f06f:7ea5de9d-b8ce-4901-b1c5-d864320c7b03_2019-05-31"


def mock_requests_response(
    status=200,
    content="CONTENT",
    json_data=None,
    raise_for_status=None,
    headers=None,
    ok=True,
):
    mock_resp = Mock()
    # mock raise_for_status call w/optional error
    mock_resp.raise_for_status = Mock()
    if raise_for_status:
        mock_resp.raise_for_status.side_effect = raise_for_status
    # set status code and content
    mock_resp.status_code = status
    mock_resp.ok = ok
    mock_resp.headers = headers if headers is not None else {}
    mock_resp.content = content
    # add json data if provided
    mock_resp.json.return_value = json_data if json_data is not None else {}
    return mock_resp


@pytest.fixture(scope="function", autouse=True)
def mock_http_error_response(mock_azure):
    response = mock_requests_response(
        status=500,
        raise_for_status=mock_azure.sdk.requests.exceptions.HTTPError(
            "500 Server Error"
        ),
    )
    return response


@pytest.fixture
def mock_get_elevated_access_token(mock_azure, monkeypatch):
    @contextmanager
    def _get_elevated_access_token(*args):
        yield "MOCK_TOKEN"

    monkeypatch.setattr(
        mock_azure, "_get_elevated_access_token", _get_elevated_access_token
    )


@pytest.fixture(scope="function")
def unmocked_cloud_provider():
    azure_cloud_provider = AzureCloudProvider(AZURE_CONFIG)
    return azure_cloud_provider


class TestLogAndRaiseExceptions:
    def test_formats_message_and_includes_response_body(
        self, mock_azure: AzureCloudProvider, mock_logger
    ):
        @log_and_raise_exceptions
        def some_func(mock_azure):
            raise mock_azure.sdk.requests.exceptions.HTTPError(
                "500 Error oh no.",
                response=mock_requests_response(status=500, json_data={"some": "json"}),
            )

        with pytest.raises(UnknownServerException):
            some_func(mock_azure)
        assert (
            mock_logger.messages[0]
            == '500 error calling some_func\n\nResponse Body:\n{"some": "json"}'
        )

    def test_handles_empty_response(self, mock_azure: AzureCloudProvider, mock_logger):
        @log_and_raise_exceptions
        def some_func(mock_azure):
            raise mock_azure.sdk.requests.exceptions.HTTPError(
                "500 Error oh no.", response=mock_requests_response(status=500),
            )

        with pytest.raises(UnknownServerException):
            some_func(mock_azure)
        assert mock_logger.messages[0] == "500 error calling some_func"


def test_create_environment_succeeds(mock_azure: AzureCloudProvider, monkeypatch):
    monkeypatch.setattr(
        mock_azure,
        "_create_management_group",
        Mock(
            return_value={
                "id": "management/group/path/TestName",
                "name": "0000000-0000-0000-0000-000000000000",
            }
        ),
    )
    payload = EnvironmentCSPPayload(
        tenant_id="1234",
        display_name="TestName",
        parent_id="management/group/path/Parent",
    )
    result = mock_azure.create_environment(payload)

    assert result.id == "management/group/path/TestName"


def test_create_application_succeeds(mock_azure: AzureCloudProvider, monkeypatch):
    payload = ApplicationCSPPayload(
        tenant_id="1234",
        display_name="Test Name",
        parent_id="management/group/path/Parent",
    )
    management_group_id = f"management/group/path/{payload.management_group_name}"
    monkeypatch.setattr(
        mock_azure,
        "_create_management_group",
        Mock(
            return_value={
                "id": management_group_id,
                "name": "0000000-0000-0000-0000-000000000000",
            }
        ),
    )

    result: ApplicationCSPResult = mock_azure.create_application(payload)
    assert result.id == management_group_id


def test_create_initial_mgmt_group_succeeds(
    mock_azure: AzureCloudProvider, monkeypatch
):
    payload = InitialMgmtGroupCSPPayload(
        tenant_id="123", display_name="A Management Group"
    )
    management_group_id = f"/providers/Microsoft.Management/managementGroups/{payload.management_group_name}"
    monkeypatch.setattr(
        mock_azure,
        "_create_management_group",
        Mock(
            return_value={
                "id": management_group_id,
                "name": payload.management_group_name,
            }
        ),
    )
    result: InitialMgmtGroupCSPResult = mock_azure.create_initial_mgmt_group(payload)

    assert result.initial_management_group_id == management_group_id
    assert result.initial_management_group_name == payload.management_group_name


def test_create_initial_mgmt_group_verification(
    mock_azure: AzureCloudProvider,
    mock_http_error_response,
    mock_get_elevated_access_token,
):
    mock_id = "management/group/path/TestName"

    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_requests_response(json_data={"id": mock_id}),
    ]

    payload = InitialMgmtGroupVerificationCSPPayload(
        tenant_id="1234",
        management_group_name="TestName",
        user_object_id="test_user_object_id",
    )

    with pytest.raises(ConnectionException):
        mock_azure.create_initial_mgmt_group_verification(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_initial_mgmt_group_verification(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_initial_mgmt_group_verification(payload)

    result: InitialMgmtGroupVerificationCSPResult = mock_azure.create_initial_mgmt_group_verification(
        payload
    )

    assert result.id == mock_id


def test_disable_user(mock_azure: AzureCloudProvider, mock_http_error_response):
    mock_azure._remove_role_assignment = Mock(return_value={"some": "data"})
    assert mock_azure.disable_user("a tenant id", "a role_assignment id") == {
        "some": "data"
    }


def test_create_tenant(mock_azure: AzureCloudProvider, mock_http_error_response):
    mock_result = mock_requests_response(
        json_data={
            "objectId": "0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d",
            "tenantId": "60ff9d34-82bf-4f21-b565-308ef0533435",
            "userId": "1153801116406515559",
        }
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    payload = TenantCSPPayload(
        **dict(
            user_id="admin",
            password="JediJan13$coot",  # pragma: allowlist secret
            domain_name="jediccpospawnedtenant2",
            first_name="Tedry",
            last_name="Tenet",
            country_code="US",
            password_recovery_email_address="thomas@promptworks.com",
        )
    )

    with pytest.raises(ConnectionException):
        mock_azure.create_tenant(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant(payload)

    result: TenantCSPResult = mock_azure.create_tenant(payload)
    assert result.tenant_id == "60ff9d34-82bf-4f21-b565-308ef0533435"


def test_create_billing_profile_creation(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response(
        headers={"Location": "http://retry-url", "Retry-After": "10",}, status=202
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = BillingProfileCreationCSPPayload(
        **dict(
            address=dict(
                address_line_1="123 S Broad Street, Suite 2400",
                company_name="Promptworks",
                city="Philadelphia",
                region="PA",
                country="US",
                postal_code="19109",
            ),
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            billing_profile_display_name="Test Billing Profile",
            billing_account_name=BILLING_ACCOUNT_NAME,
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_creation(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_creation(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_billing_profile_creation(payload)

    body: BillingProfileCreationCSPResult = mock_azure.create_billing_profile_creation(
        payload
    )
    assert body.billing_profile_retry_after == 10


def test_validate_billing_profile_creation(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(
        json_data={
            "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB",
            "name": "KQWI-W2SU-BG7-TGB",
            "status": "Succeeded",
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
                "enabledAzurePlans": [],
                "hasReadAccess": True,
                "invoiceDay": 5,
                "invoiceEmailOptIn": False,
                "invoiceSections": [
                    {
                        "id": "/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/billingProfiles/KQWI-W2SU-BG7-TGB/invoiceSections/6HMZ-2HLO-PJA-TGB",
                        "name": "6HMZ-2HLO-PJA-TGB",
                        "properties": {
                            "displayName": "First Portfolio Billing Profile"
                        },
                        "type": "Microsoft.Billing/billingAccounts/billingProfiles/invoiceSections",
                    }
                ],
            },
            "type": "Microsoft.Billing/billingAccounts/billingProfiles",
        }
    )

    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = BillingProfileVerificationCSPPayload(
        **dict(
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            billing_profile_verify_url="https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/createBillingProfile_478d5706-71f9-4a8b-8d4e-2cbaca27a668?api-version=2019-10-01-preview",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_verification(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_verification(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_billing_profile_verification(payload)

    body: BillingProfileVerificationCSPResult = mock_azure.create_billing_profile_verification(
        payload
    )
    assert body.billing_profile_name == "KQWI-W2SU-BG7-TGB"
    assert (
        body.billing_profile_properties.billing_profile_display_name
        == "First Portfolio Billing Profile"
    )


def test_create_billing_profile_tenant_access(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(
        status=201,
        json_data={
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
        },
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = BillingProfileTenantAccessCSPPayload(
        **dict(
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            user_object_id="0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d",
            billing_account_name="7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31",
            billing_profile_name="KQWI-W2SU-BG7-TGB",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_tenant_access(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_profile_tenant_access(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_billing_profile_tenant_access(payload)

    body: BillingProfileTenantAccessCSPResult = mock_azure.create_billing_profile_tenant_access(
        payload
    )
    assert (
        body.billing_role_assignment_name
        == "40000000-aaaa-bbbb-cccc-100000000000_0a5f4926-e3ee-4f47-a6e3-8b0a30a40e3d"
    )


def test_create_task_order_billing_creation(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(
        status=202,
        headers={
            "Location": "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/patchBillingProfile_KQWI-W2SU-BG7-TGB:02715576-4118-466c-bca7-b1cd3169ff46?api-version=2019-10-01-preview",
            "Retry-After": "10",
        },
    )

    mock_azure.sdk.requests.patch.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = TaskOrderBillingCreationCSPPayload(
        **dict(
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            billing_account_name="7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31",
            billing_profile_name="KQWI-W2SU-BG7-TGB",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_task_order_billing_creation(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_task_order_billing_creation(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_task_order_billing_creation(payload)

    body: TaskOrderBillingCreationCSPResult = mock_azure.create_task_order_billing_creation(
        payload
    )

    assert (
        body.task_order_billing_verify_url
        == "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/patchBillingProfile_KQWI-W2SU-BG7-TGB:02715576-4118-466c-bca7-b1cd3169ff46?api-version=2019-10-01-preview"
    )


class Test_create_task_order_billing_verification:
    @pytest.fixture
    def payload(self):
        return TaskOrderBillingVerificationCSPPayload(
            **dict(
                tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
                task_order_billing_verify_url="https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/createBillingProfile_478d5706-71f9-4a8b-8d4e-2cbaca27a668?api-version=2019-10-01-preview",
            )
        )

    def test_raises_http_error(self, mock_azure, mock_http_error_response, payload):
        mock_azure.sdk.requests.get.side_effect = [
            mock_azure.sdk.requests.exceptions.ConnectionError,
            mock_azure.sdk.requests.exceptions.Timeout,
            mock_http_error_response,
        ]
        with pytest.raises(ConnectionException):
            mock_azure.create_task_order_billing_verification(payload)
        with pytest.raises(ConnectionException):
            mock_azure.create_task_order_billing_verification(payload)
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure.create_task_order_billing_verification(payload)

    def test_raises_provisioning_error(self, mock_azure, payload):
        def make_error(status):
            return {
                "status": status,
                "error": {"code": "11235", "message": "An error occured"},
            }

        mock_azure.sdk.requests.get.side_effect = [
            mock_requests_response(json_data=make_error("Canceled")),
            mock_requests_response(json_data=make_error("Failed")),
        ]
        with pytest.raises(ResourceProvisioningError):
            mock_azure.create_task_order_billing_verification(payload)
        with pytest.raises(ResourceProvisioningError):
            mock_azure.create_task_order_billing_verification(payload)

    def test_async_operation_succeeds(self, mock_azure, payload):
        mock_result = mock_requests_response(
            json_data={
                "status": "Succeeded",
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
            },
        )
        mock_azure.sdk.requests.get.side_effect = [
            mock_result,
        ]
        body = mock_azure.create_task_order_billing_verification(payload)
        assert body.billing_profile_name == "KQWI-W2SU-BG7-TGB"
        assert (
            body.billing_profile_enabled_plan_details.enabled_azure_plans[0].get(
                "skuId"
            )
            == "0001"
        )

    def test_async_operation_in_progress(self, mock_azure, payload):
        mock_result = mock_requests_response(
            json_data={"status": "In Progress"},
            headers={"Location": "https://retry-url.com", "Retry-After": "0",},
        )
        mock_azure.sdk.requests.get.side_effect = [
            mock_result,
        ]
        body = mock_azure.create_task_order_billing_verification(payload)
        assert body.reset_stage is True
        assert body.task_order_billing_verify_url == "https://retry-url.com"
        assert body.task_order_retry_after == 0


def test_create_billing_instruction(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(
        json_data={
            "name": "TO1:CLIN001",
            "properties": {
                "amount": 1000.0,
                "endDate": "2020-03-01T00:00:00+00:00",
                "startDate": "2020-01-01T00:00:00+00:00",
            },
            "type": "Microsoft.Billing/billingAccounts/billingProfiles/billingInstructions",
        }
    )

    mock_azure.sdk.requests.put.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = BillingInstructionCSPPayload(
        **dict(
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            initial_clin_amount=1000.00,
            initial_clin_start_date="2020/1/1",
            initial_clin_end_date="2020/3/1",
            initial_clin_type="1",
            initial_task_order_id="TO1",
            billing_account_name="7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31",
            billing_profile_name="KQWI-W2SU-BG7-TGB",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_instruction(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_billing_instruction(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_billing_instruction(payload)
    body: BillingInstructionCSPResult = mock_azure.create_billing_instruction(payload)
    assert body.reported_clin_name == "TO1:CLIN001"


def test_create_product_purchase(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response(
        status=202,
        headers={
            "Location": "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/patchBillingProfile_KQWI-W2SU-BG7-TGB:02715576-4118-466c-bca7-b1cd3169ff46?api-version=2019-10-01-preview",
            "Retry-After": "10",
        },
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = ProductPurchaseCSPPayload(
        **dict(
            tenant_id="6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            billing_account_name="7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31",
            billing_profile_name="KQWI-W2SU-BG7-TGB",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_product_purchase(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_product_purchase(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_product_purchase(payload)

    body: ProductPurchaseCSPResult = mock_azure.create_product_purchase(payload)
    assert (
        body.product_purchase_verify_url
        == "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/patchBillingProfile_KQWI-W2SU-BG7-TGB:02715576-4118-466c-bca7-b1cd3169ff46?api-version=2019-10-01-preview"
    )


def test_create_product_purchase_verification(mock_azure, mock_http_error_response):

    mock_result = mock_requests_response(
        json_data={
            "id": "/providers/Microsoft.Billing/billingAccounts/BILLINGACCOUNTNAME/billingProfiles/BILLINGPROFILENAME/invoiceSections/INVOICESECTION/products/29386e29-a025-faae-f70b-b1cbbc266600",
            "name": "29386e29-a025-faae-f70b-b1cbbc266600",
            "status": "Succeeded",
            "properties": {
                "availabilityId": "C07TTFC7Q9XK",
                "billingProfileId": "/providers/Microsoft.Billing/billingAccounts/BILLINGACCOUNTNAME/billingProfiles/BILLINGPROFILENAME",
                "billingProfileDisplayName": "ATAT Billing Profile",
                "endDate": "01/30/2021",
                "invoiceSectionId": "/providers/Microsoft.Billing/billingAccounts/BILLINGACCOUNTNAME/billingProfiles/BILLINGPROFILENAME/invoiceSections/INVOICESECTION",
                "invoiceSectionDisplayName": "ATAT Billing Profile",
                "productType": "Azure Active Directory Premium P1",
                "productTypeId": "C07TTFC7Q9XK",
                "skuId": "0002",
                "skuDescription": "Azure Active Directory Premium P1",
                "purchaseDate": "01/31/2020",
                "quantity": 5,
                "status": "AutoRenew",
            },
            "type": "Microsoft.Billing/billingAccounts/billingProfiles/invoiceSections/products",
        }
    )

    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = ProductPurchaseVerificationCSPPayload(
        **dict(
            tenant_id="6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            product_purchase_verify_url="https://management.azure.com/providers/Microsoft.Billing/billingAccounts/7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31/operationResults/createBillingProfile_478d5706-71f9-4a8b-8d4e-2cbaca27a668?api-version=2019-10-01-preview",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_product_purchase_verification(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_product_purchase_verification(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_product_purchase_verification(payload)

    body: ProductPurchaseVerificationCSPResult = mock_azure.create_product_purchase_verification(
        payload
    )
    assert body.premium_purchase_date == "01/31/2020"


def test_create_tenant_principal_app(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response(json_data={"appId": "appId", "id": "id"})

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = TenantPrincipalAppCSPPayload(
        **{
            "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "display_name": "ATAT Remote Admin :: Test",
        }
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_app(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_app(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant_principal_app(payload)

    result: TenantPrincipalAppCSPResult = mock_azure.create_tenant_principal_app(
        payload
    )

    assert result.principal_app_id == "appId"


def test_create_tenant_principal(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response(json_data={"id": "principal_id"})

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = TenantPrincipalCSPPayload(
        **{
            "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "principal_app_id": "appId",
        }
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant_principal(payload)

    result: TenantPrincipalCSPResult = mock_azure.create_tenant_principal(payload)

    assert result.principal_id == "principal_id"


def test_create_tenant_principal_credential(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response(json_data={"secretText": "new secret key"})

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = TenantPrincipalCredentialCSPPayload(
        **{
            "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "principal_app_id": "appId",
            "principal_app_object_id": "appObjId",
        }
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_credential(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_credential(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant_principal_credential(payload)

    result: TenantPrincipalCredentialCSPResult = mock_azure.create_tenant_principal_credential(
        payload
    )

    assert result.principal_creds_established == True


def test_create_admin_role_definition(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(
        json_data={
            "value": [
                {"id": "wrongid", "displayName": "Wrong Role"},
                {"id": "id", "displayName": "Global Administrator"},
            ]
        }
    )

    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = AdminRoleDefinitionCSPPayload(
        **{"tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4"}
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_admin_role_definition(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_admin_role_definition(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_admin_role_definition(payload)

    result: AdminRoleDefinitionCSPResult = mock_azure.create_admin_role_definition(
        payload
    )

    assert result.admin_role_def_id == "id"


def test_create_tenant_admin_ownership(
    mock_azure: AzureCloudProvider,
    mock_http_error_response,
    mock_get_elevated_access_token,
):
    mock_result = mock_requests_response(json_data={"id": "id"})

    mock_azure.sdk.requests.put.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = TenantAdminOwnershipCSPPayload(
        **{
            "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "root_management_group_name": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "user_object_id": "971efe4d-1e80-4e39-b3b9-4e5c63ad446d",
            "root_management_group_name": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        }
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_admin_ownership(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_admin_ownership(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant_admin_ownership(payload)

    result: TenantAdminOwnershipCSPResult = mock_azure.create_tenant_admin_ownership(
        payload
    )

    assert result.admin_owner_assignment_id == "id"


def test_create_tenant_principal_ownership(
    mock_azure: AzureCloudProvider,
    mock_http_error_response,
    mock_get_elevated_access_token,
):
    mock_azure.sdk.requests.put.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_requests_response(json_data={"id": "id"}),
    ]
    payload = TenantPrincipalOwnershipCSPPayload(
        tenant_id="6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        root_management_group_name="6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        principal_id="971efe4d-1e80-4e39-b3b9-4e5c63ad446d",
        user_object_id="test_user_object_id",
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_ownership(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_tenant_principal_ownership(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_tenant_principal_ownership(payload)

    result: TenantPrincipalOwnershipCSPResult = mock_azure.create_tenant_principal_ownership(
        payload
    )

    assert result.principal_owner_assignment_id == "id"


def test_create_principal_admin_role(
    mock_azure: AzureCloudProvider, mock_http_error_response
):

    mock_result = mock_requests_response(json_data={"id": "id"})
    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = PrincipalAdminRoleCSPPayload(
        **{
            "tenant_id": uuid4().hex,
            "principal_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
            "admin_role_def_id": uuid4().hex,
        }
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_principal_admin_role(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_principal_admin_role(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_principal_admin_role(payload)

    result: PrincipalAdminRoleCSPResult = mock_azure.create_principal_admin_role(
        payload
    )

    assert result.principal_assignment_id == "id"


def test_create_subscription(mock_azure: AzureCloudProvider, mock_http_error_response):

    mock_result = mock_requests_response(
        status=202, headers={"Location": "https://verify.me", "Retry-After": 10}
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    management_group_id = str(uuid4())
    payload = SubscriptionCreationCSPPayload(
        **dict(
            tenant_id="60ff9d34-82bf-4f21-b565-308ef0533435",
            display_name="application_env_sub1",
            parent_group_id=management_group_id,
            billing_account_name="7c89b735-b22b-55c0-ab5a-c624843e8bf6:de4416ce-acc6-44b1-8122-c87c4e903c91_2019-05-31",
            billing_profile_name="KQWI-W2SU-BG7-TGB",
            invoice_section_name="6HMZ-2HLO-PJA-TGB",
        )
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_subscription(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_subscription(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_subscription(payload)

    result: SubscriptionCreationCSPResult = mock_azure.create_subscription(payload)

    assert result.subscription_verify_url == "https://verify.me"


def test_get_reporting_data(mock_azure: AzureCloudProvider, mock_http_error_response):
    mock_result = mock_requests_response(
        json_data={
            "eTag": None,
            "id": "providers/Microsoft.Billing/billingAccounts/52865e4c-52e8-5a6c-da6b-c58f0814f06f:7ea5de9d-b8ce-4901-b1c5-d864320c7b03_2019-05-31/billingProfiles/XQDJ-6LB4-BG7-TGB/invoiceSections/P73M-XC7J-PJA-TGB/providers/Microsoft.CostManagement/query/e82d0cda-2ffb-4476-a98a-425c83c216f9",
            "location": None,
            "name": "e82d0cda-2ffb-4476-a98a-425c83c216f9",
            "properties": {
                "columns": [
                    {"name": "PreTaxCost", "type": "Number"},
                    {"name": "UsageDate", "type": "Number"},
                    {"name": "InvoiceId", "type": "String"},
                    {"name": "Currency", "type": "String"},
                ],
                "nextLink": None,
                "rows": [],
            },
            "sku": None,
            "type": "Microsoft.CostManagement/query",
        }
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    # Subset of a profile's CSP data that we care about for reporting
    csp_data = {
        "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        "billing_profile_properties": {
            "invoice_sections": [
                {
                    "invoice_section_id": "providers/Microsoft.Billing/billingAccounts/52865e4c-52e8-5a6c-da6b-c58f0814f06f:7ea5de9d-b8ce-4901-b1c5-d864320c7b03_2019-05-31/billingProfiles/XQDJ-6LB4-BG7-TGB/invoiceSections/P73M-XC7J-PJA-TGB",
                }
            ],
        },
    }
    payload = CostManagementQueryCSPPayload(
        from_date=pendulum.now(tz="UTC")
        .subtract(years=1)
        .add(days=1)
        .format("YYYY-MM-DD"),
        to_date=pendulum.now(tz="UTC").format("YYYY-MM-DD"),
        **csp_data,
    )
    with pytest.raises(ConnectionException):
        mock_azure.get_reporting_data(payload, "token")
    with pytest.raises(ConnectionException):
        mock_azure.get_reporting_data(payload, "token")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.get_reporting_data(payload, "token")

    data: CostManagementQueryCSPResult = mock_azure.get_reporting_data(payload, "token")

    assert isinstance(data, CostManagementQueryCSPResult)
    assert data.name == "e82d0cda-2ffb-4476-a98a-425c83c216f9"
    assert len(data.properties.columns) == 4


def test_get_reporting_data_malformed_payload(mock_azure: AzureCloudProvider):
    mock_result = mock_requests_response()

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    # Malformed csp_data payloads that should throw pydantic validation errors
    index_error = {
        "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        "billing_profile_properties": {"invoice_sections": [],},
    }
    key_error = {
        "tenant_id": "6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        "billing_profile_properties": {"invoice_sections": [{}],},
    }

    for malformed_payload in [key_error, index_error]:
        with pytest.raises(pydantic.ValidationError):
            assert mock_azure.get_reporting_data(
                CostManagementQueryCSPPayload(
                    from_date="foo", to_date="bar", **malformed_payload,
                ),
                "token",
            )


def test_get_keyvault_token(mock_http_error_response, unmocked_cloud_provider):
    cloud_provider = unmocked_cloud_provider
    mock_result = mock_requests_response(
        status=200,
        json_data={
            "token_type": "Bearer",
            "expires_in": "3599",
            "ext_expires_in": "3599",
            "expires_on": "1588197654",
            "not_before": "1588193754",
            "resource": f"https://{cloud_provider.sdk.cloud.suffixes.keyvault_dns[1:]}",
            "access_token": "TOKEN",
        },
    )

    cloud_provider.sdk.requests.get = Mock()
    cloud_provider.sdk.requests.get.side_effect = [
        cloud_provider.sdk.requests.exceptions.ConnectionError,
        cloud_provider.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        cloud_provider._get_keyvault_token()
    with pytest.raises(ConnectionException):
        cloud_provider._get_keyvault_token()
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        cloud_provider._get_keyvault_token()

    result = cloud_provider._get_keyvault_token()
    assert result == "TOKEN"


def test_get_secret(unmocked_cloud_provider, mock_http_error_response):
    cloud_provider = unmocked_cloud_provider
    mock_result = mock_requests_response(
        status=200,
        json_data={
            "value": "mytestvalue",
            "id": "https://hybridcz-pwdev-keyvault.vault.azure.net/secrets/testsecret/abc123",
            "attributes": {
                "enabled": True,
                "created": 1588096321,
                "updated": 1588096321,
                "recoveryLevel": "Recoverable+Purgeable",
            },
        },
    )

    cloud_provider._get_keyvault_token = Mock(return_value="TOKEN")
    cloud_provider.sdk.requests.get = Mock()
    cloud_provider.sdk.requests.get.side_effect = [
        cloud_provider.sdk.requests.exceptions.ConnectionError,
        cloud_provider.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        cloud_provider.get_secret("secret key")
    with pytest.raises(ConnectionException):
        cloud_provider.get_secret("secret key")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        cloud_provider.get_secret("secret key")

    result = cloud_provider.get_secret("secret key")
    assert result == "mytestvalue"


def test_set_secret(unmocked_cloud_provider, mock_http_error_response):
    cloud_provider = unmocked_cloud_provider
    response_id = (
        f"{cloud_provider.config.get('AZURE_VAULT_URL')}secrets/testsecret/abc123"
    )
    mock_result = mock_requests_response(
        status=200,
        json_data={
            "value": "mytestvalue",
            "id": response_id,
            "attributes": {
                "enabled": True,
                "created": 1588096321,
                "updated": 1588096321,
                "recoveryLevel": "Recoverable+Purgeable",
            },
        },
    )

    cloud_provider._get_keyvault_token = Mock(return_value="TOKEN")
    cloud_provider.sdk.requests.put = Mock()
    cloud_provider.sdk.requests.put.side_effect = [
        cloud_provider.sdk.requests.exceptions.ConnectionError,
        cloud_provider.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        cloud_provider.set_secret("secret key", "mytestvalue")
    with pytest.raises(ConnectionException):
        cloud_provider.set_secret("secret key", "mytestvalue")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        cloud_provider.set_secret("secret key", "mytestvalue")

    result = cloud_provider.set_secret("secret key", "mytestvalue")
    assert result["id"] == response_id


def test_update_active_directory_user_email(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response()

    mock_azure.sdk.requests.patch.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    payload = UserCSPPayload(
        tenant_id=uuid4().hex,
        display_name="Test Testerson",
        tenant_host_name="testtenant",
        email="test@testerson.test",
        password="asdfghjkl",  # pragma: allowlist secret
    )
    with pytest.raises(ConnectionException):
        mock_azure._update_active_directory_user_email("token", uuid4().hex, payload)
    with pytest.raises(ConnectionException):
        mock_azure._update_active_directory_user_email("token", uuid4().hex, payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure._update_active_directory_user_email("token", uuid4().hex, payload)

    result = mock_azure._update_active_directory_user_email(
        "token", uuid4().hex, payload
    )

    assert result


def test_update_active_directory_user_password_profile(
    mock_azure: AzureCloudProvider, mock_http_error_response
):
    mock_result = mock_requests_response()

    mock_azure.sdk.requests.patch.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    payload = TenantAdminCredentialResetCSPPayload(
        tenant_id="6d2d2d6c-a6d6-41e1-8bb1-73d11475f8f4",
        user_object_id="acf1c3bb-2b64-4f74-8689-fb6521ae10f8",
        new_password="asdfghjkl",  # pragma: allowlist secret
    )
    with pytest.raises(ConnectionException):
        mock_azure._update_active_directory_user_password_profile("token", payload)
    with pytest.raises(ConnectionException):
        mock_azure._update_active_directory_user_password_profile("token", payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure._update_active_directory_user_password_profile("token", payload)

    result = mock_azure._update_active_directory_user_password_profile("token", payload)

    assert result


def test_create_user(mock_azure: AzureCloudProvider, mock_http_error_response):
    mock_result = mock_requests_response(json_data={"invitedUser": {"id": "id"}})

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]

    payload = UserCSPPayload(
        tenant_id=uuid4().hex,
        display_name="Test Testerson",
        tenant_host_name="testtenant",
        email="test@testerson.test",
        password="asdfghjkl",  # pragma: allowlist secret
    )

    with pytest.raises(ConnectionException):
        mock_azure.create_user(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_user(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_user(payload)

    result = mock_azure.create_user(payload)
    assert result.id == "id"


def test_create_user_role(mock_azure: AzureCloudProvider):

    mock_result_create = mock_requests_response(json_data={"id": "id"})
    mock_azure.sdk.requests.put.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_result_create,
    ]

    payload = UserRoleCSPPayload(
        tenant_id=uuid4().hex,
        user_object_id=str(uuid4()),
        management_group_id=str(uuid4()),
        role="owner",
    )
    with pytest.raises(ConnectionException):
        mock_azure.create_user_role(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_user_role(payload)
    result = mock_azure.create_user_role(payload)

    assert result.id == "id"


def test_create_user_role_failure(mock_azure: AzureCloudProvider):

    mock_azure.sdk.requests.put.side_effect = [mock_requests_response(ok=False)]

    payload = UserRoleCSPPayload(
        tenant_id=uuid4().hex,
        user_object_id=str(uuid4()),
        management_group_id=str(uuid4()),
        role="owner",
    )

    with pytest.raises(UserProvisioningException):
        mock_azure.create_user_role(payload)


def test_create_billing_owner(monkeypatch, mock_azure: AzureCloudProvider):

    final_result = "1-2-3"

    # create_billing_owner does: POST, PATCH, GET, POST

    monkeypatch.setattr(
        mock_azure,
        "_create_active_directory_user",
        Mock(return_value=UserCSPResult(id=final_result)),
    )
    # mock POST so that it pops off results in the order we want
    mock_azure.sdk.requests.post.side_effect = [
        mock_requests_response(),
    ]
    # return value for PATCH doesn't matter much
    mock_azure.sdk.requests.patch.return_value = mock_requests_response()
    # return value for GET needs to be a JSON object with a list of role definitions

    r1 = mock_requests_response(status=400)
    r2 = mock_requests_response(
        json_data={"value": [{"displayName": "Billing Administrator", "id": "4567"}]}
    )
    mock_azure.sdk.requests.get.side_effect = [r1, r2]

    payload = BillingOwnerCSPPayload(
        tenant_id=uuid4().hex,
        domain_name="rebelalliance",
        password_recovery_email_address="many@bothans.org",
    )

    result = mock_azure.create_billing_owner(payload)
    assert result.billing_owner_id == final_result


def test_create_billing_owner_uses_existing_resources(mock_azure: AzureCloudProvider):
    # mock POST so that it returns a message for an already existing role assignment
    mock_azure.sdk.requests.post.return_value = mock_requests_response(
        json_data={"error": {"message": "A conflicting objectl"}}
    )

    # return value for PATCH doesn't matter much
    mock_azure.sdk.requests.patch.return_value = mock_requests_response()

    # return value for GET needs to be a JSON object with a list of role definitions
    # Return a value for an existing user
    r1 = mock_requests_response(json_data={"displayName": "foo", "id": "1234"})
    r2 = mock_requests_response(
        json_data={"value": [{"displayName": "Billing Administrator", "id": "4567"}]}
    )
    mock_azure.sdk.requests.get.side_effect = [r1, r2]

    payload = BillingOwnerCSPPayload(
        tenant_id=uuid4().hex,
        domain_name="rebelalliance",
        password_recovery_email_address="many@bothans.org",
    )

    result = mock_azure.create_billing_owner(payload)
    assert result.billing_owner_id == "1234"


def test_update_tenant_creds(mock_azure: AzureCloudProvider, monkeypatch):

    existing_secrets = {
        "tenant_id": "mytenant",
        "tenant_admin_username": "admin",
        "tenant_admin_password": "foo",  # pragma: allowlist secret
    }
    new_secrets = {
        "tenant_id": str(uuid4()),
        "tenant_sp_client_id": str(uuid4()),
        "tenant_sp_key": "1234",
    }
    monkeypatch.setattr(
        mock_azure, "get_secret", Mock(return_value=json.dumps(existing_secrets)),
    )

    mock_new_secrets = KeyVaultCredentials(**new_secrets)
    updated_secret = mock_azure.update_tenant_creds("mytenant", mock_new_secrets)

    assert updated_secret == KeyVaultCredentials(**{**existing_secrets, **new_secrets})


def test_get_calculator_url(mock_azure: AzureCloudProvider):
    mock_result = mock_requests_response(
        status=200, json_data={"access_token": MOCK_ACCESS_TOKEN},
    )
    mock_azure.sdk.requests.get.return_value = mock_result
    assert (
        mock_azure.get_calculator_url()
        == f"{mock_azure.config.get('AZURE_CALC_URL')}?access_token={MOCK_ACCESS_TOKEN}"
    )


class TestGenerateValidDomainName:
    def test_success(self, mock_azure: AzureCloudProvider):
        tenant_name = "tenant"
        assert mock_azure.generate_valid_domain_name(tenant_name) == tenant_name

    def test_failure_after_max_tries(self, monkeypatch, mock_azure: AzureCloudProvider):
        monkeypatch.setattr(
            "atat.domain.csp.cloud.AzureCloudProvider.validate_domain_name",
            Mock(return_value=False),
        )
        with pytest.raises(DomainNameException):
            mock_azure.generate_valid_domain_name(name="test", max_tries=3)

    def test_unique(self, monkeypatch, mock_azure: AzureCloudProvider):
        # mock that a tenant exists with the name tenant_name
        tenant_name = "tenant"

        def _validate_domain_name(mock_azure, name):
            if name == tenant_name:
                return False
            else:
                return True

        monkeypatch.setattr(
            "atat.domain.csp.cloud.AzureCloudProvider.validate_domain_name",
            _validate_domain_name,
        )
        assert mock_azure.generate_valid_domain_name(tenant_name) != tenant_name


def test_create_policies(mock_azure: AzureCloudProvider, monkeypatch):
    final_assignment_id = "whatever"
    put_results = [
        mock_requests_response(
            json_data={"id": "foo", "properties": {"displayName": "foo"}}, status=201
        ),
        mock_requests_response(
            json_data={"id": "bar", "properties": {"displayName": "bar"}}, status=201
        ),
        mock_requests_response(
            json_data={"id": "baz", "properties": {"displayName": "baz"}}, status=201
        ),
        mock_requests_response(
            json_data={
                "id": "test_id",
                "policyType": "Custom",
                "name": "test_name",
                "properties": {"displayName": "test_display_name"},
            },
            status=201,
        ),
        mock_requests_response(json_data={"id": final_assignment_id}, status=201),
    ]
    mock_session = Mock
    mock_session.put = Mock(side_effect=put_results)
    monkeypatch.setattr("requests.Session", mock_session)

    payload = PoliciesCSPPayload(
        tenant_id="1234", root_management_group_name=str(uuid4()),
    )
    result: PoliciesCSPResult = mock_azure.create_policies(payload)
    assert result.policy_assignment_id == final_assignment_id


def test_get_service_principal_token_fails(mock_azure, monkeypatch):
    monkeypatch.setattr(
        atat.domain.csp.cloud.azure_cloud_provider,
        "get_principal_auth_token",
        Mock(return_value=None),
    )
    with pytest.raises(AuthenticationException):
        mock_azure._get_service_principal_token("tenant_id", "client", "secret")


class TestCreateManagementGroup:
    def test_status_code_200(self, mock_azure: AzureCloudProvider, monkeypatch):
        mock_session_object = Mock()
        mock_session_object.put = Mock(
            return_value=mock_requests_response(status=200, json_data={"some": "data"})
        )
        mock_azure.sdk.requests.Session.return_value = mock_session_object
        result = mock_azure._create_management_group(
            "management_group_id", "display_name", "tenant_id"
        )
        assert result == {"some": "data"}

    def test_status_code_202(self, mock_azure: AzureCloudProvider, monkeypatch):
        # Mock session object
        mock_session_object = Mock()
        mock_session_object.put = Mock(
            return_value=mock_requests_response(
                status=202,
                headers={
                    "Azure-AsyncOperation": "http://status_url.com",
                    "Location": "http://result_url.com",
                },
            )
        )
        mock_azure.sdk.requests.Session.return_value = mock_session_object

        # Mock _poll_management_group_creation_job
        mock_poll_management_group_creation_job = Mock()
        monkeypatch.setattr(
            mock_azure,
            "_poll_management_group_creation_job",
            mock_poll_management_group_creation_job,
        )

        mock_azure._create_management_group(
            "management_group_id", "display_name", "tenant_id"
        )
        mock_poll_management_group_creation_job.assert_called_once_with(
            "http://status_url.com", "http://result_url.com", mock_session_object
        )

    def test_raises_exceptions(
        self, mock_azure: AzureCloudProvider, mock_http_error_response
    ):
        put_results = [
            mock_azure.sdk.requests.exceptions.ConnectionError,
            mock_azure.sdk.requests.exceptions.Timeout,
            mock_http_error_response,
        ]
        mock_session_object = Mock()
        mock_session_object.put = Mock(side_effect=put_results)
        mock_azure.sdk.requests.Session.return_value = mock_session_object

        with pytest.raises(ConnectionException):
            mock_azure._create_management_group(
                "management_group_id", "display_name", "tenant_id"
            )
        with pytest.raises(ConnectionException):
            mock_azure._create_management_group(
                "management_group_id", "display_name", "tenant_id"
            )
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure._create_management_group(
                "management_group_id", "display_name", "tenant_id"
            )


class TestPollManagementGroupCreationJob:
    def test_succeeds(self, mock_azure):
        mock_session_object = Mock()
        mock_session_object.get = Mock(
            side_effect=[
                mock_requests_response(
                    headers={"Retry-After": 0}, json_data={"status": "In Progress"}
                ),
                mock_requests_response(
                    headers={"Retry-After": 0}, json_data={"status": "In Progress"}
                ),
                mock_requests_response(
                    headers={"Retry-After": 0}, json_data={"status": "Succeeded"}
                ),
                mock_requests_response(
                    headers={"Retry-After": 0}, json_data={"status": "Succeeded"}
                ),
            ]
        )
        mock_azure.sdk.requests.Session.return_value = mock_session_object

        result = mock_azure._poll_management_group_creation_job(
            "status_url", "result_url", mock_session_object
        )

        calls = [
            call("status_url"),
            call("status_url"),
            call("status_url"),
            call("result_url"),
        ]
        mock_session_object.get.assert_has_calls(calls)
        assert result["status"] == "Succeeded"

    def test_provisioning_error(self, mock_azure):
        def make_error(status):
            return {
                "status": status,
                "error": {"code": "11234", "message": "An error occured"},
            }

        mock_session_object = Mock()
        mock_session_object.get = Mock(
            side_effect=[
                mock_requests_response(json_data=make_error("Canceled")),
                mock_requests_response(json_data=make_error("Failed")),
            ]
        )
        mock_azure.sdk.requests.Session.return_value = mock_session_object

        with pytest.raises(ResourceProvisioningError):
            mock_azure._poll_management_group_creation_job(
                "status", "result", mock_session_object
            )
        with pytest.raises(ResourceProvisioningError):
            mock_azure._poll_management_group_creation_job(
                "status", "result", mock_session_object
            )

    def test_http_error(self, mock_azure, mock_http_error_response):
        mock_session_object = Mock()
        mock_session_object.get = Mock(
            side_effect=[
                mock_azure.sdk.requests.exceptions.ConnectionError,
                mock_azure.sdk.requests.exceptions.Timeout,
                mock_http_error_response,
            ]
        )
        mock_azure.sdk.requests.Session.return_value = mock_session_object

        with pytest.raises(ConnectionException):
            mock_azure._poll_management_group_creation_job(
                "status_url", "result_url", mock_session_object
            )
        with pytest.raises(ConnectionException):
            mock_azure._poll_management_group_creation_job(
                "status_url", "result_url", mock_session_object
            )
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure._poll_management_group_creation_job(
                "status_url", "result_url", mock_session_object
            )


class TestGetBillingAdminRoleTemplateId:
    def test_returns_template_id(self, mock_azure):
        mock_azure.sdk.requests.get.return_value = mock_requests_response(
            json_data={
                "value": [
                    {
                        "description": "description-value",
                        "displayName": "Billing Administrator",
                        "id": "id-value",
                    }
                ]
            }
        )
        result = mock_azure._get_billing_admin_role_template_id("MOCK_TOKEN")
        assert result == "id-value"

    def test_raises_provisioning_error(self, mock_azure):
        mock_azure.sdk.requests.get.return_value = mock_requests_response(
            json_data={
                "value": [
                    {
                        "description": "description-value",
                        "displayName": "Something Random",
                        "id": "id-value",
                    }
                ]
            }
        )
        with pytest.raises(UserProvisioningException):
            mock_azure._get_billing_admin_role_template_id("MOCK_TOKEN")

    def test_raises_http_errors(self, mock_azure, mock_http_error_response):
        mock_azure.sdk.requests.get.side_effect = [
            mock_azure.sdk.requests.exceptions.ConnectionError,
            mock_azure.sdk.requests.exceptions.Timeout,
            mock_http_error_response,
        ]
        with pytest.raises(ConnectionException):
            mock_azure._get_billing_admin_role_template_id("MOCK_TOKEN")
        with pytest.raises(ConnectionException):
            mock_azure._get_billing_admin_role_template_id("MOCK_TOKEN")
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure._get_billing_admin_role_template_id("MOCK_TOKEN")


class TestActivateBillingAdminRole:
    def test_returns_role_id(self, mock_azure):
        mock_azure.sdk.requests.post.return_value = mock_requests_response(
            json_data={
                "description": "description-value",
                "displayName": "displayName-value",
                "roleTemplateId": "roleTemplateId-value",
                "id": "id-value",
            }
        )
        result = mock_azure._activate_billing_admin_role("MOCK_TOKEN", "123456789")
        assert result == "id-value"

    def test_raises_http_errors(self, mock_azure, mock_http_error_response):
        mock_azure.sdk.requests.post.side_effect = [
            mock_azure.sdk.requests.exceptions.ConnectionError,
            mock_azure.sdk.requests.exceptions.Timeout,
            mock_http_error_response,
        ]
        with pytest.raises(ConnectionException):
            mock_azure._activate_billing_admin_role("MOCK_TOKEN", "123456789")
        with pytest.raises(ConnectionException):
            mock_azure._activate_billing_admin_role("MOCK_TOKEN", "123456789")
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure._activate_billing_admin_role("MOCK_TOKEN", "123456789")


def test_activate_and_return_billing_admin_role_id(mock_azure, monkeypatch):
    token = "MOCK_TOKEN"
    template_id = 12345

    mock_get_billing_admin_role_template_id = Mock(return_value=template_id)
    mock_activate_billing_admin_role = Mock()
    monkeypatch.setattr(
        mock_azure,
        "_get_billing_admin_role_template_id",
        mock_get_billing_admin_role_template_id,
    )
    monkeypatch.setattr(
        mock_azure, "_activate_billing_admin_role", mock_activate_billing_admin_role,
    )

    mock_azure._activate_and_return_billing_admin_role_id(token)

    mock_get_billing_admin_role_template_id.assert_called_once_with(token)
    mock_activate_billing_admin_role.assert_called_once_with(token, template_id)


class TestExtractServicePrincipalFromQuery:
    def test_succeeds(self, mock_azure):
        response = mock_requests_response(
            json_data={"value": ["service_principal_object"]}
        )
        sp = mock_azure._extract_service_principal_from_query(response)
        assert sp == "service_principal_object"

    def test_throws_error(self, mock_azure):
        response = mock_requests_response(json_data={"value": []})
        with pytest.raises(ResourceProvisioningError):
            mock_azure._extract_service_principal_from_query(response)


class TestExtractAppRoleFromServicePrincipal:
    def test_finds_target(self, mock_azure):
        service_principal = {
            "appRoles": [{"value": "Another.Value"}, {"value": "Target.Value"}]
        }
        ar = mock_azure._extract_app_role_from_service_principal(
            service_principal, "Target.Value"
        )
        assert ar == {"value": "Target.Value"}

    def test_throws_error_for_empty_list(self, mock_azure):
        service_principal = {"appRoles": []}
        with pytest.raises(ResourceProvisioningError):
            mock_azure._extract_app_role_from_service_principal(
                service_principal, "Target.Value"
            )

    def test_throws_error_for_missing_target(self, mock_azure):
        service_principal = {"appRoles": [{"value": "Another.Value"}]}
        with pytest.raises(ResourceProvisioningError):
            mock_azure._extract_app_role_from_service_principal(
                service_principal, "Target.Value"
            )


def test_create_principal_app_graph_api_permissions(
    mock_azure, monkeypatch, mock_http_error_response
):
    monkeypatch.setattr(
        mock_azure,
        "_get_graph_sp_and_user_invite_app_role_ids",
        Mock(return_value=("graph_api_sp_object_id", "user_invite_app_role_id")),
    )

    mock_azure._get_user_principal_token_for_scope = Mock(
        return_value=MOCK_ACCESS_TOKEN
    )

    mock_azure.sdk.requests.post.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_requests_response(status=201),
    ]

    payload = PrincipalAppGraphApiPermissionsCSPPayload(
        tenant_id="tenant_id", principal_id="principal_id"
    )

    with pytest.raises(ConnectionException):
        mock_azure.create_principal_app_graph_api_permissions(payload)
    with pytest.raises(ConnectionException):
        mock_azure.create_principal_app_graph_api_permissions(payload)
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure.create_principal_app_graph_api_permissions(payload)

    assert mock_azure.create_principal_app_graph_api_permissions(payload)


def test_get_graph_sp_and_user_invite_app_role_ids(
    mock_azure, mock_http_error_response
):
    mock_result = mock_requests_response(
        json_data={
            "value": [
                {
                    "id": "service_principal_object_id",
                    "appRoles": [
                        {"id": "app_role_id", "value": "Directory.ReadWrite.All"}
                    ],
                }
            ]
        }
    )
    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        mock_azure._get_graph_sp_and_user_invite_app_role_ids("token")
    with pytest.raises(ConnectionException):
        mock_azure._get_graph_sp_and_user_invite_app_role_ids("token")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure._get_graph_sp_and_user_invite_app_role_ids("token")

    assert (
        "service_principal_object_id",
        "app_role_id",
    ) == mock_azure._get_graph_sp_and_user_invite_app_role_ids("token")


def test_list_role_assignments(mock_azure, mock_http_error_response):
    mock_result = mock_requests_response(json_data={"value": []})
    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        mock_azure._list_role_assignments("token")
    with pytest.raises(ConnectionException):
        mock_azure._list_role_assignments("token")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure._list_role_assignments("token")

    assert [] == mock_azure._list_role_assignments("token")


def test_list_role_definitions(mock_azure, mock_http_error_response):
    mock_result = mock_requests_response(json_data={"value": []})
    mock_azure.sdk.requests.get.side_effect = [
        mock_azure.sdk.requests.exceptions.ConnectionError,
        mock_azure.sdk.requests.exceptions.Timeout,
        mock_http_error_response,
        mock_result,
    ]
    with pytest.raises(ConnectionException):
        mock_azure._list_role_definitions("token")
    with pytest.raises(ConnectionException):
        mock_azure._list_role_definitions("token")
    with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
        mock_azure._list_role_definitions("token")

    assert [] == mock_azure._list_role_definitions("token")


class Test_remove_role_assignment:
    def test_errors(self, mock_azure, mock_http_error_response):
        mock_azure.sdk.requests.delete.side_effect = [
            mock_azure.sdk.requests.exceptions.ConnectionError,
            mock_azure.sdk.requests.exceptions.Timeout,
            mock_http_error_response,
        ]
        with pytest.raises(ConnectionException):
            mock_azure._remove_role_assignment("token", "assignment-id")
        with pytest.raises(ConnectionException):
            mock_azure._remove_role_assignment("token", "assignment-id")
        with pytest.raises(UnknownServerException, match=r".*500 Server Error.*"):
            mock_azure._remove_role_assignment("token", "assignment-id")

    def test_success(self, mock_azure, mock_http_error_response):
        mock_azure.sdk.requests.delete.side_effect = [
            mock_requests_response(json_data={"some": "data"})
        ]
        assert {"some": "data"} == mock_azure._remove_role_assignment(
            "token", "role-assignment-id"
        )


class Test_get_role_definition_id:
    def test_interpolates_definition_name(self, mock_azure, monkeypatch):
        monkeypatch.setattr(
            mock_azure,
            "_list_role_definitions",
            Mock(return_value=[{"name": "definition_UUID"}]),
        )
        mock_azure._get_role_definition_id("token", "A definition")
        mock_azure._list_role_definitions.assert_called_with(
            "token", params={"$filter": "roleName eq 'A definition'"}
        )

    def test_returns_name(self, mock_azure, monkeypatch):
        monkeypatch.setattr(
            mock_azure,
            "_list_role_definitions",
            Mock(return_value=[{"name": "definition_UUID"}]),
        )
        assert (
            mock_azure._get_role_definition_id("token", "A definition")
            == "definition_UUID"
        )

    def test_returns_none_for_empty_list(self, mock_azure, monkeypatch):
        monkeypatch.setattr(mock_azure, "_list_role_definitions", Mock(return_value=[]))

        assert mock_azure._get_role_definition_id("token", "A definition") is None


def test_filter_role_assignments(mock_azure):
    target_role_assignment = {
        "properties": {"roleDefinitionId": "fully/pathed/role_definition_id"}
    }
    wrong_role_assignment = {
        "properties": {"roleDefinitionId": "full/path/wrong_definition_id"}
    }
    assert (
        mock_azure._filter_role_assignments(
            [target_role_assignment], "role_definition_id"
        )
        == target_role_assignment
    )
    assert (
        mock_azure._filter_role_assignments(
            [wrong_role_assignment], "role_definition_id"
        )
        is None
    )

    assert mock_azure._filter_role_assignments([], "role_definition_id") is None


class Test_remove_tenant_admin_elevated_access:
    def test_role_assignment_found(self, mock_azure, monkeypatch):
        monkeypatch.setattr(
            mock_azure,
            "_get_role_definition_id",
            Mock(return_value="role_definition_id"),
        )
        monkeypatch.setattr(
            mock_azure,
            "_list_role_assignments",
            Mock(
                return_value=[
                    {
                        "id": "assignment_id",
                        "properties": {
                            "roleDefinitionId": "fully/pathed/role_definition_id",
                            "more": "data",
                        },
                    }
                ]
            ),
        )
        monkeypatch.setattr(
            mock_azure, "_remove_role_assignment", Mock(return_value={"some": "data"})
        )

        assert mock_azure._remove_tenant_admin_elevated_access(
            "mock_tenant_id", "mock_object_id", token="MOCK_ELEVATED_ACCESS_TOKEN"
        )

    def test_role_assignment_not_found(self, mock_azure, monkeypatch, mock_logger):
        mock_azure._get_user_principal_token_for_scope = Mock()
        mock_azure._get_user_principal_token_for_scope.return_value = MOCK_ACCESS_TOKEN
        monkeypatch.setattr(mock_azure, "_get_role_definition_id", Mock())
        monkeypatch.setattr(mock_azure, "_list_role_assignments", Mock())
        monkeypatch.setattr(
            mock_azure, "_filter_role_assignments", Mock(return_value=None)
        )
        assert mock_azure._remove_tenant_admin_elevated_access(
            "mock_tenant_id", "mock_object_id", token="MOCK_ELEVATED_ACCESS_TOKEN"
        )
        log_msg = mock_logger.messages[0]
        assert "mock_tenant_id" in log_msg
        assert "mock_object_id" in log_msg

    def test_list_role_assignments_raises_authz_error(
        self, mock_azure, monkeypatch, mock_logger
    ):
        monkeypatch.setattr(
            mock_azure, "_get_role_definition_id", Mock(return_value="definition_id")
        )
        mock_azure.sdk.requests.get.side_effect = [
            mock_requests_response(
                raise_for_status=mock_azure.sdk.requests.exceptions.HTTPError(
                    "403 Authorization Error",
                    response=mock_requests_response(status=403),
                ),
            )
        ]

        assert mock_azure._remove_tenant_admin_elevated_access(
            "mock_tenant_id", "mock_object_id", token="MOCK_ELEVATED_ACCESS_TOKEN"
        )
        _remove_tenant_admin_elevated_access_warning = mock_logger.messages[1]
        assert "mock_tenant_id" in _remove_tenant_admin_elevated_access_warning

    def test_list_role_assignments_raises_other_error(
        self, mock_azure, monkeypatch, mock_logger
    ):
        mock_azure._get_user_principal_token_for_scope = Mock()
        mock_azure._get_user_principal_token_for_scope.return_value = MOCK_ACCESS_TOKEN
        monkeypatch.setattr(
            mock_azure, "_get_role_definition_id", Mock(return_value="definition_id")
        )
        mock_azure.sdk.requests.get.side_effect = [
            mock_requests_response(
                raise_for_status=mock_azure.sdk.requests.exceptions.HTTPError(
                    "500 Server Error", response=mock_requests_response(status=500),
                ),
            )
        ]
        with pytest.raises(UnknownServerException):
            mock_azure._remove_tenant_admin_elevated_access(
                "mock_tenant_id", "mock_object_id", token="MOCK_ELEVATED_ACCESS_TOKEN"
            )

    class Test_get_elevated_access_token:
        @pytest.fixture(autouse=True)
        def patch_submethods(self, mock_azure, monkeypatch):
            monkeypatch.setattr(
                mock_azure,
                "_get_tenant_admin_token",
                Mock(side_effect=["MOCK_TOKEN", "MOCK_ELEVATED_TOKEN"]),
            )
            monkeypatch.setattr(
                mock_azure, "_elevate_tenant_admin_access", Mock(),
            )
            monkeypatch.setattr(
                mock_azure, "_remove_tenant_admin_elevated_access", Mock(),
            )

        def test_token_elevation_fails(self, mock_azure):
            mock_azure._elevate_tenant_admin_access.side_effect = [
                AuthenticationException("uh oh")
            ]
            with pytest.raises(AuthenticationException):
                with mock_azure._get_elevated_access_token(
                    "tenant_id", "user_object_id"
                ) as _:
                    pass

        def test_get_token(self, mock_azure, mock_logger):
            with mock_azure._get_elevated_access_token(
                "tenant_id", "user_object_id"
            ) as elevated_token:
                pass
            assert elevated_token == "MOCK_ELEVATED_TOKEN"
            assert len(mock_logger.messages) == 2

        def test_remove_elevated_access_fails(self, mock_azure, mock_logger):
            mock_azure._remove_tenant_admin_elevated_access.side_effect = [
                mock_azure.sdk.requests.exceptions.ConnectionError
            ]
            with pytest.raises(Exception):
                with mock_azure._get_elevated_access_token(
                    "tenant_id", "user_object_id"
                ) as _:
                    pass
            assert len(mock_logger.messages) == 2

        def test_second_token_request_fails(self, mock_azure, monkeypatch):
            monkeypatch.setattr(
                mock_azure,
                "_get_tenant_admin_token",
                Mock(side_effect=["MOCK_TOKEN", AuthenticationException("weird")]),
            )
            with pytest.raises(AuthenticationException):
                with mock_azure._get_elevated_access_token(
                    "tenant_id", "user_object_id"
                ) as _:
                    mock_azure._remove_tenant_admin_elevated_access.assert_called_with(
                        "tenant_id", "user_object_id", token="MOCK_TOKEN"
                    )

        def test_remove_elevated_access_called_after_exception(
            self, mock_azure, mock_logger
        ):
            with pytest.raises(Exception):
                with mock_azure._get_elevated_access_token(
                    "tenant_id", "user_object_id"
                ) as elevated_token:
                    raise Exception
            mock_azure._remove_tenant_admin_elevated_access.assert_called_once_with(
                "tenant_id", "user_object_id", token=elevated_token
            )
