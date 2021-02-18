from smtplib import SMTPException
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pendulum
import pytest
from azure.core.exceptions import AzureError

from atat.domain.csp.cloud import MockCloudProvider
from atat.domain.csp.cloud.exceptions import ConnectionException, GeneralCSPException
from atat.domain.csp.cloud.models import (
    SubscriptionCreationCSPPayload,
    UserRoleCSPResult,
)
from atat.domain.csp.cloud.utils import OFFICE_365_DOMAIN
from atat.jobs import (
    RecordFailure,
    build_subscription_payload,
    create_billing_instruction,
    create_environment,
    dispatch_create_application,
    dispatch_create_environment,
    dispatch_create_environment_role,
    dispatch_create_user,
    dispatch_provision_portfolio,
    do_create_application,
    do_create_environment,
    do_create_environment_role,
    do_create_subscription,
    do_create_user,
    do_provision_portfolio,
    log_do_create_environment,
    make_initial_csp_data,
    provision_portfolio,
    send_ppoc_email,
    send_task_order_files,
)
from atat.models import (
    ApplicationRoleStatus,
    EnvironmentRoleStatus,
    JobFailure,
    Portfolio,
    PortfolioStates,
)
from atat.models.mixins.state_machines import AzureStages
from atat.utils.localization import translate
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


@pytest.fixture(autouse=True, scope="function")
def csp():
    return Mock(
        wraps=MockCloudProvider(
            {}, with_delay=False, with_failure=False, with_authorization=False
        )
    )


@pytest.fixture(scope="function")
def portfolio():
    portfolio = PortfolioFactory.create()
    return portfolio


def _find_failure(session, entity, id_):
    return (
        session.query(JobFailure)
        .filter(JobFailure.entity == entity)
        .filter(JobFailure.entity_id == id_)
        .one()
    )


def test_environment_job_failure(session, celery_app, celery_worker):
    @celery_app.task(bind=True, base=RecordFailure)
    def _fail_hard(self, environment_id=None):
        raise ValueError("something bad happened")

    environment = EnvironmentFactory.create()
    celery_worker.reload()

    # Use apply instead of delay since we are testing the on_failure hook only
    task = _fail_hard.apply(kwargs={"environment_id": environment.id})
    with pytest.raises(ValueError):
        task.get()

    job_failure = _find_failure(session, "environment", str(environment.id))
    assert job_failure.task == task


def test_environment_role_job_failure(session, celery_app, celery_worker):
    @celery_app.task(bind=True, base=RecordFailure)
    def _fail_hard(self, environment_role_id=None):
        raise ValueError("something bad happened")

    role = EnvironmentRoleFactory.create()
    celery_worker.reload()

    # Use apply instead of delay since we are testing the on_failure hook only
    task = _fail_hard.apply(kwargs={"environment_role_id": role.id})
    with pytest.raises(ValueError):
        task.get()

    job_failure = _find_failure(session, "environment_role", str(role.id))
    assert job_failure.task == task


NOW = pendulum.now(tz="UTC")
YESTERDAY = NOW.subtract(days=1)
TOMORROW = NOW.add(days=1)


def test_create_environment_job(session, csp):
    environment = EnvironmentFactory.create()
    environment.application.cloud_id = "parentId"
    environment.portfolio.csp_data = {"tenant_id": "fake"}
    session.add(environment)
    session.commit()

    do_create_environment(csp, environment.id)
    session.refresh(environment)

    assert environment.cloud_id


def test_create_environment_job_is_idempotent(csp, session):
    environment = EnvironmentFactory.create(cloud_id=uuid4().hex)
    do_create_environment(csp, environment.id)

    csp.create_environment.assert_not_called()


def test_create_application_job(session, csp):
    portfolio = PortfolioFactory.create(
        csp_data={"tenant_id": str(uuid4()), "root_management_group_name": str(uuid4())}
    )
    application = ApplicationFactory.create(portfolio=portfolio, cloud_id=None)
    do_create_application(csp, application.id)
    session.refresh(application)

    assert application.cloud_id


def test_create_application_job_is_idempotent(csp):
    application = ApplicationFactory.create(cloud_id=uuid4())
    do_create_application(csp, application.id)

    csp.create_application.assert_not_called()


class TestCreateUserJob:
    @pytest.fixture
    def portfolio(self, app):
        return PortfolioFactory.create(
            csp_data={
                "tenant_id": str(uuid4()),
                "domain_name": f"rebelalliance.{OFFICE_365_DOMAIN}",
            }
        )

    @pytest.fixture
    def app_1(self, portfolio):
        return ApplicationFactory.create(portfolio=portfolio, cloud_id="321")

    @pytest.fixture
    def app_2(self, portfolio):
        return ApplicationFactory.create(portfolio=portfolio, cloud_id="123")

    @pytest.fixture
    def user(self):
        return UserFactory.create(
            first_name="Han", last_name="Solo", email="han@example.com"
        )

    @pytest.fixture
    def app_role_1(self, app_1, user):
        return ApplicationRoleFactory.create(
            application=app_1,
            user=user,
            status=ApplicationRoleStatus.ACTIVE,
            cloud_id=None,
        )

    @pytest.fixture
    def app_role_2(self, app_2, user):
        return ApplicationRoleFactory.create(
            application=app_2,
            user=user,
            status=ApplicationRoleStatus.ACTIVE,
            cloud_id=None,
        )

    def test_create_user_job(self, session, csp, app_role_1):
        assert not app_role_1.cloud_id

        session.begin_nested()
        do_create_user(csp, [app_role_1.id])
        session.rollback()

        assert app_role_1.cloud_id

    def test_create_user_sends_email(self, monkeypatch, csp, app_role_1, app_role_2):
        mock = Mock()
        monkeypatch.setattr("atat.jobs.send_mail", mock)

        do_create_user(csp, [app_role_1.id, app_role_2.id])
        assert mock.call_count == 1

    def test_user_has_tenant(self, session, csp, app_role_1, app_1, user):
        cloud_id = "123456"
        ApplicationRoleFactory.create(
            user=user,
            status=ApplicationRoleStatus.ACTIVE,
            cloud_id=cloud_id,
            application=ApplicationFactory.create(portfolio=app_1.portfolio),
        )

        session.begin_nested()
        do_create_user(csp, [app_role_1.id])
        session.rollback()

        assert app_role_1.cloud_id == cloud_id


def test_dispatch_create_environment(session, monkeypatch):
    # Given that I have a portfolio with an active CLIN and two environments,
    # one of which is deleted
    portfolio = PortfolioFactory.create(
        applications=[{"environments": [{}, {}], "cloud_id": uuid4().hex}],
        task_orders=[
            {"create_clins": [{"start_date": YESTERDAY, "end_date": TOMORROW,}]}
        ],
    )
    [e1, e2] = portfolio.applications[0].environments
    e2.deleted = True
    session.add(e2)
    session.commit()

    mock = Mock()
    monkeypatch.setattr("atat.jobs.create_environment", mock)

    # When dispatch_create_environment is called
    dispatch_create_environment.run()

    # It should cause the create_environment task to be called once with the
    # non-deleted environment
    mock.delay.assert_called_once_with(environment_id=e1.id)


def test_dispatch_create_application(monkeypatch):
    portfolio = PortfolioFactory.create(state="COMPLETED")
    app = ApplicationFactory.create(portfolio=portfolio)

    mock = Mock()
    monkeypatch.setattr("atat.jobs.create_application", mock)

    # When dispatch_create_application is called
    dispatch_create_application.run()

    # It should cause the create_application task to be called once
    # with the application id
    mock.delay.assert_called_once_with(application_id=app.id)


def test_dispatch_create_user(monkeypatch):
    application = ApplicationFactory.create(cloud_id="123")
    user = UserFactory.create(
        first_name="Han", last_name="Solo", email="han@example.com"
    )
    app_role = ApplicationRoleFactory.create(
        application=application,
        user=user,
        status=ApplicationRoleStatus.ACTIVE,
        cloud_id=None,
    )

    mock = Mock()
    monkeypatch.setattr("atat.jobs.create_user", mock)

    # When dispatch_create_user is called
    dispatch_create_user.run()

    # It should cause the create_user task to be called once
    # with the application id
    mock.delay.assert_called_once_with(application_role_ids=[app_role.id])


def test_create_environment_no_dupes(session):
    portfolio = PortfolioFactory.create(
        applications=[{"environments": [{"cloud_id": uuid4().hex}]}],
        task_orders=[
            {"create_clins": [{"start_date": YESTERDAY, "end_date": TOMORROW,}]}
        ],
    )
    environment = portfolio.applications[0].environments[0]

    # create_environment is run twice on the same environment
    create_environment.run(environment_id=environment.id)
    session.refresh(environment)

    first_cloud_id = environment.cloud_id

    create_environment.run(environment_id=environment.id)
    session.refresh(environment)

    # The environment's cloud_id was not overwritten in the second run
    assert environment.cloud_id == first_cloud_id

    # The environment's claim was released
    assert environment.claimed_until == None


def test_dispatch_provision_portfolio(csp, monkeypatch):
    portfolio = PortfolioFactory.create(
        task_orders=[
            {
                "create_clins": [{"start_date": YESTERDAY, "end_date": TOMORROW,}],
                "signed_at": NOW,
            }
        ],
    )
    sm = PortfolioStateMachineFactory.create(portfolio=portfolio)
    mock = Mock()
    monkeypatch.setattr("atat.jobs.provision_portfolio", mock)
    dispatch_provision_portfolio.run()
    mock.delay.assert_called_once_with(portfolio_id=portfolio.id)


class TestDoProvisionPortfolio:
    @patch("atat.models.PortfolioStateMachine.trigger_next_transition")
    def test_portfolio_has_state_machine(
        self, trigger_next_transition, csp, session, portfolio
    ):
        do_provision_portfolio(csp=csp, portfolio_id=portfolio.id)
        assert portfolio.state_machine
        csp_data = make_initial_csp_data(portfolio)
        trigger_next_transition.assert_called_with(csp_data=csp_data)

    @patch("atat.jobs.send_ppoc_email")
    def test_sends_email_to_PPOC_on_completion(
        self, send_ppoc_email, monkeypatch, csp, portfolio: Portfolio
    ):
        sm: PortfolioStateMachine = PortfolioStateMachineFactory.create(
            portfolio=portfolio
        )

        # The stage before "COMPLETED"
        last_step = [e.name for e in AzureStages][-1]
        sm.state = getattr(PortfolioStates, f"{last_step}_CREATED")
        do_provision_portfolio(csp=csp, portfolio_id=portfolio.id)

        send_ppoc_email.assert_called_once()


def test_send_ppoc_email(monkeypatch, app):
    mock = Mock()
    monkeypatch.setattr("atat.jobs.send_mail", mock)

    ppoc_email = "example@example.com"
    user_id = "userid"
    domain_name = "domain"

    send_ppoc_email(
        {
            "password_recovery_email_address": ppoc_email,
            "user_id": user_id,
            "domain_name": domain_name,
        }
    )
    mock.assert_called_once_with(
        recipients=[ppoc_email],
        subject=translate("email.portfolio_ready.subject"),
        body=translate(
            "email.portfolio_ready.body",
            {
                "password_reset_address": app.config.get("AZURE_LOGIN_URL"),
                "username": f"{user_id}@{domain_name}.{OFFICE_365_DOMAIN}",
            },
        ),
    )


class TestProvisionPortfolio:
    @patch("atat.jobs.do_provision_portfolio")
    def test_calls_do_provision_portfolio(self, do_provision_portfolio, app, portfolio):
        provision_portfolio(portfolio.id)
        do_provision_portfolio.assert_called_with(
            app.csp.cloud, portfolio_id=portfolio.id
        )


def test_dispatch_create_environment_role(monkeypatch):
    portfolio = PortfolioFactory.create(csp_data={"tenant_id": "123"})
    app_role = ApplicationRoleFactory.create(
        application=ApplicationFactory.create(portfolio=portfolio),
        status=ApplicationRoleStatus.ACTIVE,
        cloud_id="123",
    )
    env_role = EnvironmentRoleFactory.create(application_role=app_role)

    mock = Mock()
    monkeypatch.setattr("atat.jobs.create_environment_role", mock)

    dispatch_create_environment_role.run()

    mock.delay.assert_called_once_with(environment_role_id=env_role.id)


class TestCreateEnvironmentRole:
    @pytest.fixture
    def env_role(self):
        portfolio = PortfolioFactory.create(csp_data={"tenant_id": "123"})
        app = ApplicationFactory.create(portfolio=portfolio)
        app_role = ApplicationRoleFactory.create(
            application=app, status=ApplicationRoleStatus.ACTIVE, cloud_id="123",
        )
        env = EnvironmentFactory.create(application=app, cloud_id="123")
        return EnvironmentRoleFactory.create(
            environment=env, application_role=app_role, cloud_id=None
        )

    @pytest.fixture
    def csp(self):
        csp = MagicMock()
        csp.create_user_role.return_value = UserRoleCSPResult(id="a-cloud-id")
        return csp

    def test_success(self, env_role, csp, session):
        session.begin_nested()
        do_create_environment_role(csp, environment_role_id=env_role.id)
        session.rollback()
        assert env_role.cloud_id == "a-cloud-id"
        assert env_role.status == EnvironmentRoleStatus.ACTIVE

    def test_sends_email(self, monkeypatch, env_role, csp):
        send_mail = Mock()
        monkeypatch.setattr("atat.jobs.send_mail", send_mail)
        do_create_environment_role(csp, environment_role_id=env_role.id)
        assert send_mail.call_count == 1


class TestSendTaskOrderFiles:
    @pytest.fixture(scope="function")
    def send_mail(self, monkeypatch):
        mock = Mock()
        monkeypatch.setattr("atat.jobs.send_mail", mock)
        return mock

    @pytest.fixture(scope="function")
    def download_task_order(self, monkeypatch):
        def _download_task_order(MockFileService, object_name):
            return {
                "name": object_name,
                "filename": "test.pdf",
                "content": b"some content",
            }

        monkeypatch.setattr(
            "atat.domain.csp.files.MockFileService.download_task_order",
            _download_task_order,
        )

    def test_sends_multiple_emails(self, send_mail, download_task_order):
        # Create 3 Task Orders
        for i in range(3):
            TaskOrderFactory.create(create_clins=[{"number": "0001"}])

        send_task_order_files.run()

        # Check that send_with_attachment was called once for each task order
        assert send_mail.call_count == 3

    def test_kwargs(self, send_mail, download_task_order, app):
        task_order = TaskOrderFactory.create(create_clins=[{"number": "0001"}])
        send_task_order_files.run()

        # Check that send_with_attachment was called with correct kwargs
        send_mail.assert_called_once_with(
            recipients=[app.config.get("MICROSOFT_TASK_ORDER_EMAIL_ADDRESS")],
            subject=translate(
                "email.task_order_sent.subject", {"to_number": task_order.number}
            ),
            body=translate(
                "email.task_order_sent.body", {"to_number": task_order.number}
            ),
            attachments=[
                {
                    "name": task_order.pdf.object_name,
                    "maintype": "application",
                    "subtype": "pdf",
                    "filename": "test.pdf",
                    "content": b"some content",
                }
            ],
        )
        assert task_order.pdf_last_sent_at

    def test_send_failure(self, monkeypatch):
        def _raise_smtp_exception(**kwargs):
            raise SMTPException

        monkeypatch.setattr("atat.jobs.send_mail", _raise_smtp_exception)
        task_order = TaskOrderFactory.create(create_clins=[{"number": "0001"}])
        send_task_order_files.run()

        # Check that pdf_last_sent_at has not been updated
        assert not task_order.pdf_last_sent_at

    def test_download_failure(self, send_mail, monkeypatch):
        def _download_task_order(MockFileService, object_name):
            raise AzureError("something went wrong")

        monkeypatch.setattr(
            "atat.domain.csp.files.MockFileService.download_task_order",
            _download_task_order,
        )
        task_order = TaskOrderFactory.create(create_clins=[{"number": "0002"}])
        send_task_order_files.run()

        # Check that pdf_last_sent_at has not been updated
        assert not task_order.pdf_last_sent_at

    def test_integration(self, app, monkeypatch):
        """Only mocks out the connection on the mailer so that we can test that
        the job runs end-to-end.
        """
        connection = Mock()
        monkeypatch.setattr(app.mailer, "connection", connection)
        task_order = TaskOrderFactory.create(create_clins=[{"number": "0002"}])
        send_task_order_files.run()
        assert connection.send.called


class TestCreateBillingInstructions:
    @pytest.fixture
    def unsent_clin(self):
        start_date = YESTERDAY
        portfolio = PortfolioFactory.create(
            csp_data={
                "tenant_id": str(uuid4()),
                "billing_account_name": "fake",
                "billing_profile_name": "fake",
            },
            task_orders=[{"create_clins": [{"start_date": start_date}]}],
            state=PortfolioStates.COMPLETED.name,
        )
        return portfolio.task_orders[0].clins[0]

    def test_update_clin_last_sent_at(self, session, unsent_clin):
        assert not unsent_clin.last_sent_at

        # The session needs to be nested to prevent detached SQLAlchemy instance
        session.begin_nested()
        create_billing_instruction()

        # check that last_sent_at has been updated
        assert unsent_clin.last_sent_at
        session.rollback()

    def test_failure(self, monkeypatch, session, unsent_clin):
        def _create_billing_instruction(MockCloudProvider, object_name):
            raise AzureError("something went wrong")

        monkeypatch.setattr(
            "atat.domain.csp.cloud.MockCloudProvider.create_billing_instruction",
            _create_billing_instruction,
        )

        # The session needs to be nested to prevent detached SQLAlchemy instance
        session.begin_nested()
        create_billing_instruction()

        # check that last_sent_at has not been updated
        assert not unsent_clin.last_sent_at
        session.rollback()

    def test_task_order_with_multiple_clins(self, session):
        start_date = YESTERDAY
        portfolio = PortfolioFactory.create(
            csp_data={
                "tenant_id": str(uuid4()),
                "billing_account_name": "fake",
                "billing_profile_name": "fake",
            },
            task_orders=[
                {
                    "create_clins": [
                        {"start_date": start_date, "last_sent_at": start_date}
                    ]
                }
            ],
            state=PortfolioStates.COMPLETED.name,
        )
        task_order = portfolio.task_orders[0]
        sent_clin = task_order.clins[0]

        # Add new CLIN to the Task Order
        new_clin = CLINFactory.create(task_order=task_order)
        assert not new_clin.last_sent_at

        session.begin_nested()
        create_billing_instruction()
        session.add(sent_clin)

        # check that last_sent_at has been update for the new clin only
        assert new_clin.last_sent_at
        assert sent_clin.last_sent_at != new_clin.last_sent_at
        session.rollback()


class Test_make_initial_csp_data:
    @pytest.fixture
    def portfolio(self):
        return PortfolioFactory.create()

    def contains_dictionary(self, subset, superset):
        return all(item in superset.items() for item in subset.items())

    def test_no_csp_data(self, portfolio):
        data = make_initial_csp_data(portfolio)
        assert portfolio.csp_data is None
        assert isinstance(data, dict)

    def test_has_csp_data(self):
        extra_csp_data = {"foo": "bar"}
        portfolio = PortfolioFactory.create(csp_data=extra_csp_data)
        data = make_initial_csp_data(portfolio)
        assert self.contains_dictionary(extra_csp_data, data)

    def test_includes_portfolio_details(self, portfolio):
        data = make_initial_csp_data(portfolio)
        assert self.contains_dictionary(portfolio.to_dictionary(), data)

    def test_includes_billing_account_name(self, app, portfolio):
        data = make_initial_csp_data(portfolio)
        billing_account = app.config["AZURE_BILLING_ACCOUNT_NAME"]
        assert data.get("billing_account_name") == billing_account


def test_log_do_create_environment(mock_logger):
    log_do_create_environment("foo", "bar", "baz")
    assert len(mock_logger.messages) == 3


class Test_do_create_subscription:
    @pytest.fixture
    def environment(self):
        env = EnvironmentFactory(
            cloud_id=f"/providers/Microsoft.Management/managementGroups/an_id"
        )
        env.portfolio.csp_data = {
            "billing_account_name": "xxxx-xxxx-xxx-xxx",
            "billing_profile_name": "xxxxxxxxxxx:xxxxxxxxxxxxx_xxxxxx",
            "tenant_id": "xxxxxxxxxxx-xxxxxxxxxx-xxxxxxx-xxxxx",
            "billing_profile_properties": {
                "invoice_sections": [{"invoice_section_name": "xxxx-xxxx-xxx-xxx"}]
            },
        }
        return env

    def test_do_create_subscription(self, app, csp, environment):
        do_create_subscription(csp, environment.id)
        csp.create_subscription.assert_called()

    def test_do_create_subscription_fails(self, app, csp, environment, mock_logger):
        csp.create_subscription.side_effect = [GeneralCSPException()]
        with pytest.raises(GeneralCSPException):
            do_create_subscription(csp, environment.id)
            assert len(mock_logger.messages) == 1


class TestBuildSubscriptionPayload:
    def test_unique_display_name(self):
        # Create 2 Applications with the same name that both have an environment named 'Environment'
        app_1 = ApplicationFactory.create(
            name="Application", environments=[{"name": "Environment", "cloud_id": 123}]
        )
        env_1 = app_1.environments[0]
        app_2 = ApplicationFactory.create(
            name="Application", environments=[{"name": "Environment", "cloud_id": 456}]
        )
        env_2 = app_2.environments[0]
        env_1.portfolio.csp_data = {
            "billing_account_name": "xxxx-xxxx-xxx-xxx",
            "billing_profile_name": "xxxxxxxxxxx:xxxxxxxxxxxxx_xxxxxx",
            "tenant_id": "xxxxxxxxxxx-xxxxxxxxxx-xxxxxxx-xxxxx",
            "billing_profile_properties": {
                "invoice_sections": [{"invoice_section_name": "xxxx-xxxx-xxx-xxx"}]
            },
        }
        env_2.portfolio.csp_data = {
            "billing_account_name": "xxxx-xxxx-xxx-xxx",
            "billing_profile_name": "xxxxxxxxxxx:xxxxxxxxxxxxx_xxxxxx",
            "tenant_id": "xxxxxxxxxxx-xxxxxxxxxx-xxxxxxx-xxxxx",
            "billing_profile_properties": {
                "invoice_sections": [{"invoice_section_name": "xxxx-xxxx-xxx-xxx"}]
            },
        }

        # Create subscription payload for each environment
        payload_1 = build_subscription_payload(env_1)
        payload_2 = build_subscription_payload(env_2)

        assert payload_1.display_name != payload_2.display_name

    def test_populates_payload_correctly(self, app):
        application = ApplicationFactory.create(
            name="Application", environments=[{"name": "Environment", "cloud_id": 123}]
        )
        environment = application.environments[0]
        account_name = app.config["AZURE_BILLING_ACCOUNT_NAME"]
        profile_name = "fake-profile-name"
        tenant_id = "123"
        section_name = "fake-section-name"

        environment.portfolio.csp_data = {
            "billing_profile_name": profile_name,
            "tenant_id": tenant_id,
            "billing_profile_properties": {
                "invoice_sections": [{"invoice_section_name": section_name}]
            },
        }
        payload = build_subscription_payload(environment)

        assert type(payload) == SubscriptionCreationCSPPayload
        # Check all key/value pairs except for display_name because of the appended random string
        expected_items = [
            ("tenant_id", tenant_id),
            ("parent_group_id", environment.cloud_id),
            ("billing_account_name", account_name),
            ("billing_profile_name", profile_name),
            ("invoice_section_name", section_name),
        ]
        payload_items = payload.dict().items()
        for item in expected_items:
            assert item in payload_items
