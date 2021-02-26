import os
from time import sleep
from uuid import uuid4

import pendulum
import pytest

from atat.domain.csp import CSP
from atat.domain.csp.cloud.exceptions import UnknownServerException
from atat.domain.csp.cloud.hybrid_cloud_provider import HybridCloudProvider
from atat.domain.csp.cloud.models import (
    CostManagementQueryCSPPayload,
    SubscriptionCreationCSPPayload,
)
from atat.domain.csp.cloud.utils import make_auth_header
from atat.jobs import (
    do_create_application,
    do_create_environment,
    do_create_environment_role,
    do_create_user,
)
from atat.models import ApplicationRoleStatus, PortfolioStateMachine, PortfolioStates
from tests.factories import (
    ApplicationFactory,
    ApplicationRoleFactory,
    CLINFactory,
    EnvironmentFactory,
    EnvironmentRoleFactory,
    PortfolioFactory,
    PortfolioStateMachineFactory,
    TaskOrderFactory,
    UserFactory,
)


@pytest.fixture(scope="session")
def csp(app):
    csp = CSP(
        "hybrid",
        app.config,
        with_delay=False,
        with_failure=False,
        with_authorization=False,
    ).cloud

    return csp


def _create_active_taskorder(factory: TaskOrderFactory, portfolio):
    """
    Since some of the fixtures in this module are scoped to the test session
    and others to the function, they cannot easily share fixtures in common.
    In order to DRY up some of the code, this method takes the
    TaskOrderFactory as an argument. That way pytest does not object about
    whether the SQLAlchemy session fixture underlying the factory is session
    or function-scoped.
    """
    today = pendulum.today(tz="UTC")
    yesterday = today.subtract(days=1)
    future = today.add(days=100)

    return factory.create(
        portfolio=portfolio,
        signed_at=yesterday,
        clins=[CLINFactory.create(start_date=yesterday, end_date=future)],
    )


@pytest.mark.hybrid
class TestIntegration:
    @pytest.fixture(scope="session")
    def portfolio(self, csp, app):
        owner = UserFactory.create()
        portfolio = PortfolioFactory.create(owner=owner,)

        _create_active_taskorder(TaskOrderFactory, portfolio)

        return portfolio

    @pytest.fixture(scope="function")
    def tenant_id(self, portfolio):
        return portfolio.csp_data["tenant_id"]

    @pytest.fixture(scope="function")
    def user_object_id(self, portfolio):
        return portfolio.csp_data["user_object_id"]

    @pytest.fixture(scope="session")
    def user(self):
        first_name = f"test-user-{uuid4()}"
        return UserFactory.create(
            first_name=first_name, last_name="Solo", email=f"{first_name}@example.com"
        )

    @pytest.fixture(scope="session")
    def application(self, portfolio):
        return ApplicationFactory.create(portfolio=portfolio, cloud_id=None)

    @pytest.fixture(scope="session")
    def app_role(self, application, user):
        return ApplicationRoleFactory.create(
            application=application,
            user=user,
            status=ApplicationRoleStatus.ACTIVE,
            cloud_id=None,
        )

    @pytest.fixture(scope="session")
    def environment(self, application):
        return EnvironmentFactory.create(application=application, cloud_id=None)

    @pytest.fixture(scope="session")
    def env_role(self, app_role, environment):
        return EnvironmentRoleFactory.create(
            environment=environment, application_role=app_role
        )

    @pytest.fixture(scope="session")
    def state_machine(self, app, csp, portfolio):
        return PortfolioStateMachineFactory.create(portfolio=portfolio, cloud=csp)

    def _get_management_group(self, csp, tenant_id, management_group_id):
        sp_token = csp.azure._get_tenant_principal_token(tenant_id)
        response = csp.azure.sdk.requests.get(
            f"{csp.azure.sdk.cloud.endpoints.resource_manager}{management_group_id}?api-version=2020-02-01",
            headers=make_auth_header(sp_token),
        )
        response.raise_for_status()
        return response.json()

    @pytest.mark.depends(name="portfolio")
    def test_hybrid_provision_portfolio(self, state_machine: PortfolioStateMachine):
        csp_data = {}
        config = {"billing_account_name": "billing_account_name"}

        self.portfolio = state_machine.portfolio
        self.csp = state_machine.cloud

        while state_machine.state != PortfolioStates.COMPLETED:
            collected_data = dict(
                list(csp_data.items())
                + list(state_machine.portfolio.to_dictionary().items())
                + list(config.items())
            )

            state_machine.trigger_next_transition(csp_data=collected_data)
            # TODO: The _get_service_principal_token method call within
            # create_initial_mgmt_group fails periodically. There must be some kind
            # of race condition on the Azure side we're not accounting for. This
            # sleep is temporary and we should solve the race condition.
            sleep(2)
            assert (
                "created" in state_machine.state.value
                or state_machine.state == PortfolioStates.COMPLETED
            )

            csp_data = state_machine.portfolio.csp_data

    @pytest.mark.depends(on=["portfolio"])
    def test_hybrid_access_not_elevated(self, csp, tenant_id, env_role):
        """By the end of portfolio provisioning, access should not be elevated"""

        token = csp.azure._get_tenant_admin_token(
            tenant_id, csp.azure.sdk.cloud.endpoints.resource_manager + "/.default"
        )
        with pytest.raises(UnknownServerException):
            # "Asserts" that the tenant admin no longer has elevated access
            # since "_list_role_assignments" requires elevated acces
            csp.azure._list_role_assignments(token)

    @pytest.mark.depends(on=["portfolio"])
    def test_context_manager_removes_access(self, csp, tenant_id, user_object_id):
        """Specifically test the behavior of the access manager. Elevating
        access allows a call to an API function that requires it, and trying the
        same function again without the context manager raises an exception """

        with csp.azure._get_elevated_access_token(
            tenant_id, user_object_id
        ) as elevated_token:
            assert csp.azure._list_role_assignments(
                elevated_token,
                params={"$filter": f"principalId eq '{user_object_id}'"},
            )

        token = csp.azure._get_tenant_admin_token(
            tenant_id, csp.azure.sdk.cloud.endpoints.resource_manager + "/.default"
        )
        with pytest.raises(UnknownServerException):
            csp.azure._list_role_assignments(
                token, params={"$filter": f"principalId eq '{user_object_id}'"}
            )

    @pytest.mark.depends(name="application", on=["portfolio"])
    def test_hybrid_create_application_job(self, csp, application, tenant_id, session):
        do_create_application(csp, application.id)
        session.refresh(application)

        assert application.cloud_id

        mgmt_grp_resp = self._get_management_group(csp, tenant_id, application.cloud_id)

        # the portfolio management group should be the parent of the management
        # group we just created for the application
        assert (
            application.portfolio.csp_data["tenant_id"]
            in mgmt_grp_resp["properties"]["details"]["parent"]["id"]
        )

    @pytest.mark.depends(name="environment", on=["application"])
    def test_hybrid_create_environment_job(self, csp, environment, tenant_id, session):
        do_create_environment(csp, environment.id)
        session.refresh(environment)

        assert environment.cloud_id

        mgmt_grp_resp = self._get_management_group(csp, tenant_id, environment.cloud_id)

        # the application management group should be the parent of the management
        # group we just created for the environment
        assert (
            environment.application.cloud_id
            in mgmt_grp_resp["properties"]["details"]["parent"]["id"]
        )

    @pytest.mark.depends(name="user", on=["application"])
    def test_hybrid_create_user_job(self, session, csp, app_role, portfolio):
        assert not app_role.cloud_id

        session.begin_nested()
        do_create_user(csp, [app_role.id])
        session.rollback()

        assert app_role.cloud_id

    @pytest.mark.depends(name="environment_role", on=["user", "environment"])
    def test_hybrid_do_create_environment_role_job(self, session, csp, env_role):
        assert env_role.cloud_id is None

        session.begin_nested()
        do_create_environment_role(csp, env_role.id)
        session.rollback()

        assert env_role.cloud_id

    @pytest.mark.depends(on=["environment_role"])
    def test_hybrid_disable_user(self, csp, user, tenant_id, env_role):
        env_role_cloud_id = env_role.cloud_id
        disable_user_result = csp.disable_user(tenant_id, env_role_cloud_id)
        assert disable_user_result["id"] == env_role_cloud_id


@pytest.mark.hybrid
def test_get_reporting_data(csp, app):
    """This test requires credentials for an app registration that has the
    "Invoice Section Reader" role for the invoice section scope being queried.
    """

    from_date = (
        pendulum.now(tz="UTC").subtract(years=1).add(days=1).format("YYYY-MM-DD")
    )
    to_date = pendulum.now(tz="UTC").format("YYYY-MM-DD")

    payload = CostManagementQueryCSPPayload(
        tenant_id=csp.azure.root_tenant_id,
        from_date=from_date,
        to_date=to_date,
        billing_profile_properties={"invoice_sections": [{"invoice_section_id": "",}],},
    )

    result = csp.get_reporting_data(payload)
    assert result.name


@pytest.mark.subscriptions
def test_create_subscription(csp):
    root_tenant_id = csp.azure.root_tenant_id
    payload = SubscriptionCreationCSPPayload(
        display_name=f"{HybridCloudProvider.HYBRID_PREFIX} Subscription Creation Test",
        tenant_id=root_tenant_id,
        parent_group_id=f"/providers/Microsoft.Management/managementGroups/subscription-creation-test",
        billing_account_name=csp.azure.config["AZURE_BILLING_ACCOUNT_NAME"],
        billing_profile_name=csp.azure.config["AZURE_BILLING_PROFILE_ID"],
        invoice_section_name=csp.azure.config["AZURE_INVOICE_SECTION_ID"],
    )

    subscription_creation_token = csp.azure._get_service_principal_token(
        root_tenant_id,
        os.environ["AZURE_SUBSCRIPTION_CREATION_CLIENT_ID"],
        os.environ["AZURE_SUBSCRIPTION_CREATION_SECRET"],
    )
    subscription_creation_result = csp.azure.create_subscription(
        payload, token=subscription_creation_token
    )
    assert subscription_creation_result.subscription_verify_url
    assert subscription_creation_result.subscription_retry_after
