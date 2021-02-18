import unittest

import pytest

from atat.domain.csp import CSP, MockCloudProvider
from atat.domain.csp.cloud.models import (
    BillingProfileCreationCSPPayload,
    BillingProfileCreationCSPResult,
    EnvironmentCSPPayload,
    EnvironmentCSPResult,
    TenantCSPPayload,
    TenantCSPResult,
)
from tests.factories import EnvironmentFactory, EnvironmentRoleFactory, UserFactory

CREDENTIALS = MockCloudProvider(config={})._auth_credentials


@pytest.fixture
def mock_csp():
    return MockCloudProvider(
        config={}, with_delay=False, with_failure=False, with_authorization=False
    )


def test_create_environment(mock_csp: MockCloudProvider):
    environment = EnvironmentFactory.create()
    environment.application.cloud_id = "parent_id"
    environment.portfolio.csp_data = {"tenant_id": "fake"}
    payload = EnvironmentCSPPayload(
        **dict(
            tenant_id=environment.portfolio.csp_data.get("tenant_id"),
            display_name=environment.name,
            parent_id=environment.application.cloud_id,
        )
    )
    result = mock_csp.create_environment(payload)
    assert isinstance(result, EnvironmentCSPResult)


def test_create_tenant(mock_csp: MockCloudProvider):
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
    result = mock_csp.create_tenant(payload)
    assert isinstance(result, TenantCSPResult)


def test_create_billing_profile_creation(mock_csp: MockCloudProvider):

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
            billing_account_name="123123",
        )
    )
    result = mock_csp.create_billing_profile_creation(payload)
    assert isinstance(result, BillingProfileCreationCSPResult)


def test_create_or_update_user(mock_csp: MockCloudProvider):
    env_role = EnvironmentRoleFactory.create()
    csp_user_id = mock_csp.create_or_update_user(CREDENTIALS, env_role, "csp_role_id")
    assert isinstance(csp_user_id, str)


def test_disable_user(mock_csp: MockCloudProvider):
    assert mock_csp.disable_user("tenant_id", "role_assignment_cloud_id")


class CspTestError(unittest.TestCase):
    def test_value_error_raised_incorrect_csp(self):
        """
        Checks to make sure a value that is not "hybrid", "mock", "mock-test", and "azure" raises an exception

        """
        with self.assertRaises(ValueError):
            CSP("Foo", {})
