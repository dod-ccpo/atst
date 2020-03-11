import pendulum
import pytest
from uuid import uuid4

from atat.models import CSPRole, ApplicationRoleStatus
from atat.domain.application_roles import ApplicationRoles
from atat.domain.applications import Applications
from atat.domain.environment_roles import EnvironmentRoles
from atat.domain.exceptions import AlreadyExistsError, NotFoundError
from atat.domain.permission_sets import PermissionSets

from tests.factories import (
    ApplicationFactory,
    ApplicationRoleFactory,
    EnvironmentFactory,
    EnvironmentRoleFactory,
    PortfolioFactory,
    UserFactory,
)


def test_create_application_with_multiple_environments():
    portfolio = PortfolioFactory.create()
    application = Applications.create(
        portfolio.owner, portfolio, "My Test Application", "Test", ["dev", "prod"]
    )

    assert application.portfolio == portfolio
    assert application.name == "My Test Application"
    assert application.description == "Test"
    assert sorted(e.name for e in application.environments) == ["dev", "prod"]


def test_portfolio_owner_can_view_environments():
    owner = UserFactory.create()
    portfolio = PortfolioFactory.create(
        owner=owner,
        applications=[{"environments": [{"name": "dev"}, {"name": "prod"}]}],
    )
    application = Applications.get(portfolio.applications[0].id)

    assert len(application.environments) == 2


def test_can_only_update_name_and_description():
    owner = UserFactory.create()
    portfolio = PortfolioFactory.create(
        owner=owner,
        applications=[
            {
                "name": "Application 1",
                "description": "a application",
                "environments": [{"name": "dev"}],
            }
        ],
    )
    application = Applications.get(portfolio.applications[0].id)
    env_name = application.environments[0].name
    Applications.update(
        application,
        {
            "name": "New Name",
            "description": "a new application",
            "environment_name": "prod",
        },
    )

    assert application.name == "New Name"
    assert application.description == "a new application"
    assert len(application.environments) == 1
    assert application.environments[0].name == env_name


def test_get_excludes_deleted():
    app = ApplicationFactory.create(deleted=True)
    with pytest.raises(NotFoundError):
        Applications.get(app.id)


def test_get_application():
    app = ApplicationFactory.create()
    assert Applications.get(app.id) == app
    assert Applications.get(app.id, portfolio_id=app.portfolio_id) == app
    with pytest.raises(NotFoundError):
        # make the uuid a string like you'd get from a route
        rando_id = str(uuid4())
        Applications.get(app.id, portfolio_id=rando_id)


def test_delete_application(session):
    app = ApplicationFactory.create()
    app_role = ApplicationRoleFactory.create(user=UserFactory.create(), application=app)
    env1 = EnvironmentFactory.create(application=app)
    env2 = EnvironmentFactory.create(application=app)
    assert not app.deleted
    assert not env1.deleted
    assert not env2.deleted
    assert not app_role.deleted

    Applications.delete(app)

    assert app.deleted
    assert env1.deleted
    assert env2.deleted
    assert app_role.deleted

    # changes are flushed
    assert not session.dirty


def test_for_user():
    user = UserFactory.create()
    portfolio = PortfolioFactory.create()
    for _x in range(4):
        ApplicationFactory.create(portfolio=portfolio)

    ApplicationRoleFactory.create(
        application=portfolio.applications[0],
        user=user,
        status=ApplicationRoleStatus.ACTIVE,
    )
    ApplicationRoleFactory.create(
        application=portfolio.applications[1],
        user=user,
        status=ApplicationRoleStatus.ACTIVE,
    )
    ApplicationRoleFactory.create(
        application=portfolio.applications[2],
        user=user,
        status=ApplicationRoleStatus.PENDING,
    )

    assert len(portfolio.applications) == 4
    user_applications = Applications.for_user(user, portfolio)
    assert len(user_applications) == 2


class TestInvite:
    @pytest.fixture
    def application(self):
        return ApplicationFactory.create()

    @pytest.fixture
    def env1(self, application):
        return EnvironmentFactory.create(application=application)

    @pytest.fixture
    def env2(self, application):
        return EnvironmentFactory.create(application=application)

    @pytest.fixture
    def user_data(self):
        return UserFactory.dictionary()

    def test_success(self, application, env1, env2, user_data):
        invitation = Applications.invite(
            application=application,
            inviter=application.portfolio.owner,
            user_data=user_data,
            permission_sets_names=[PermissionSets.EDIT_APPLICATION_TEAM],
            environment_roles_data=[
                {"environment_id": env1.id, "role": CSPRole.ADMIN},
                {"environment_id": env2.id, "role": None},
            ],
            cloud_id="123",
        )

        member_role = invitation.role
        assert invitation.dod_id == user_data["dod_id"]
        # view application AND edit application team
        assert len(member_role.permission_sets) == 2

        env_roles = member_role.environment_roles
        assert len(env_roles) == 1
        assert env_roles[0].environment == env1

    def test_nonexistent_environment(self, application, env1, user_data):
        with pytest.raises(NotFoundError):
            Applications.invite(
                application=application,
                inviter=application.portfolio.owner,
                user_data=user_data,
                environment_roles_data=[
                    {"environment_id": env1.id, "role": CSPRole.ADMIN},
                    {"environment_id": uuid4(), "role": CSPRole.ADMIN},
                ],
                cloud_id="123",
            )

    def test_no_cloud_id(self, application, user_data):
        invitation = Applications.invite(
            application=application,
            inviter=application.portfolio.owner,
            user_data=user_data,
            permission_sets_names=[PermissionSets.EDIT_APPLICATION_TEAM],
            cloud_id=None,
        )

        assert invitation.role.cloud_id is None

    def test_cloud_id_set_in_app_role(self, application, user_data):
        cloud_id = "123456"
        invitation = Applications.invite(
            application=application,
            inviter=application.portfolio.owner,
            user_data=user_data,
            permission_sets_names=[PermissionSets.EDIT_APPLICATION_TEAM],
            cloud_id=cloud_id,
        )

        assert invitation.role.cloud_id == cloud_id


def test_create_does_not_duplicate_names_within_portfolio():
    portfolio = PortfolioFactory.create()
    name = "An Awesome Application"

    assert Applications.create(portfolio.owner, portfolio, name, "")
    with pytest.raises(AlreadyExistsError):
        Applications.create(portfolio.owner, portfolio, name, "")


def test_update_does_not_duplicate_names_within_portfolio():
    portfolio = PortfolioFactory.create()
    name = "An Awesome Application"
    application = ApplicationFactory.create(portfolio=portfolio, name=name)
    dupe_application = ApplicationFactory.create(portfolio=portfolio)

    with pytest.raises(AlreadyExistsError):
        Applications.update(dupe_application, {"name": name})


def test_get_applications_pending_creation():
    now = pendulum.now(tz="utc")
    later = now.add(minutes=30)

    portfolio1 = PortfolioFactory.create(state="COMPLETED")
    app_ready = ApplicationFactory.create(portfolio=portfolio1)

    app_done = ApplicationFactory.create(portfolio=portfolio1, cloud_id="123456")

    portfolio2 = PortfolioFactory.create(state="UNSTARTED")
    app_not_ready = ApplicationFactory.create(portfolio=portfolio2)

    uuids = Applications.get_applications_pending_creation()

    assert [app_ready.id] == uuids
