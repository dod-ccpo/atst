import pytest

from atat.domain.application_roles import ApplicationRoles
from atat.domain.exceptions import NotFoundError
from atat.utils.utilities import sort_nested
from tests.factories import (
    ApplicationFactory,
    ApplicationRoleFactory,
    ApplicationRoleStatus,
    EnvironmentFactory,
    EnvironmentRoleFactory,
    PermissionSets,
    PortfolioFactory,
    UserFactory,
)


def test_create_application_role():
    application = ApplicationFactory.create()
    user = UserFactory.create()

    application_role = ApplicationRoles.create(
        application=application,
        user=user,
        permission_set_names=[PermissionSets.EDIT_APPLICATION_TEAM],
    )

    assert application_role.permission_sets == PermissionSets.get_many(
        [PermissionSets.EDIT_APPLICATION_TEAM, PermissionSets.VIEW_APPLICATION]
    )
    assert application_role.application == application
    assert application_role.user == user


def test_enabled_application_role():
    application = ApplicationFactory.create()
    user = UserFactory.create()
    app_role = ApplicationRoleFactory.create(
        application=application, user=user, status=ApplicationRoleStatus.DISABLED
    )
    assert app_role.status == ApplicationRoleStatus.DISABLED

    ApplicationRoles.enable(app_role, app_role.user)

    assert app_role.status == ApplicationRoleStatus.ACTIVE


def test_get():
    user = UserFactory.create()
    application = ApplicationFactory.create()
    app_role = ApplicationRoleFactory.create(user=user, application=application)

    assert ApplicationRoles.get(user.id, application.id)
    assert app_role.application == application
    assert app_role.user == user


def test_get_handles_invalid_id():
    user = UserFactory.create()
    application = ApplicationFactory.create()

    with pytest.raises(NotFoundError):
        ApplicationRoles.get(user.id, application.id)


def test_get_by_id():
    user = UserFactory.create()
    application = ApplicationFactory.create()
    app_role = ApplicationRoleFactory.create(user=user, application=application)

    assert ApplicationRoles.get_by_id(app_role.id) == app_role
    app_role.status = ApplicationRoleStatus.DISABLED

    with pytest.raises(NotFoundError):
        ApplicationRoles.get_by_id(app_role.id)


def test_disable(session):
    application = ApplicationFactory.create()
    user = UserFactory.create()
    member_role = ApplicationRoleFactory.create(
        application=application, user=user, status=ApplicationRoleStatus.ACTIVE
    )
    environment = EnvironmentFactory.create(application=application)
    environment_role = EnvironmentRoleFactory.create(
        application_role=member_role, environment=environment
    )
    assert member_role.status == ApplicationRoleStatus.ACTIVE

    ApplicationRoles.disable(member_role)
    session.refresh(member_role)
    session.refresh(environment_role)
    assert member_role.status == ApplicationRoleStatus.DISABLED
    assert environment_role.deleted


def test_get_pending_creation():

    # ready Applications belonging to the same Portfolio
    portfolio_one = PortfolioFactory.create()
    ready_app = ApplicationFactory.create(cloud_id="123", portfolio=portfolio_one)
    ready_app2 = ApplicationFactory.create(cloud_id="321", portfolio=portfolio_one)

    # ready Application belonging to a new Portfolio
    ready_app3 = ApplicationFactory.create(cloud_id="567")
    unready_app = ApplicationFactory.create()

    # two distinct Users
    user_one = UserFactory.create()
    user_two = UserFactory.create()

    # Two ApplicationRoles belonging to the same User and
    # different Applications. These should sort together because
    # they are all under the same portfolio (portfolio_one).
    role_one = ApplicationRoleFactory.create(
        user=user_one, application=ready_app, status=ApplicationRoleStatus.ACTIVE
    )
    role_two = ApplicationRoleFactory.create(
        user=user_one, application=ready_app2, status=ApplicationRoleStatus.ACTIVE
    )

    # An ApplicationRole belonging to a different User. This will
    # be included but sort separately because it belongs to a
    # different user.
    role_three = ApplicationRoleFactory.create(
        user=user_two, application=ready_app, status=ApplicationRoleStatus.ACTIVE
    )

    # An ApplicationRole belonging to one of the existing users
    # but under a different portfolio. It will sort separately.
    role_four = ApplicationRoleFactory.create(
        user=user_one, application=ready_app3, status=ApplicationRoleStatus.ACTIVE
    )

    # This ApplicationRole will not be in the results because its
    # application is not ready (implicitly, its cloud_id is not
    # set.)
    ApplicationRoleFactory.create(
        user=UserFactory.create(),
        application=unready_app,
        status=ApplicationRoleStatus.ACTIVE,
    )

    # This ApplicationRole will not be in the results because it
    # does not have a user associated.
    ApplicationRoleFactory.create(
        user=None, application=ready_app, status=ApplicationRoleStatus.ACTIVE,
    )

    # This ApplicationRole will not be in the results because its
    # status is not ACTIVE.
    ApplicationRoleFactory.create(
        user=UserFactory.create(),
        application=unready_app,
        status=ApplicationRoleStatus.DISABLED,
    )

    app_ids = ApplicationRoles.get_pending_creation()
    expected_ids = [[role_one.id, role_two.id], [role_three.id], [role_four.id]]
    # Sort the list and the lists in it and then compare them.
    assert sort_nested(app_ids) == sort_nested(expected_ids)


def test_get_many():
    ar1 = ApplicationRoleFactory.create()
    ar2 = ApplicationRoleFactory.create()
    ApplicationRoleFactory.create()

    result = ApplicationRoles.get_many([ar1.id, ar2.id])
    assert result == [ar1, ar2]


class TestGetCloudIdForUser:
    @pytest.fixture
    def user(self):
        return UserFactory.create(dod_id=1234567890)

    @pytest.fixture
    def portfolio(self):
        return PortfolioFactory.create()

    def test_app_role_provisioned_same_portfolio(self, user, portfolio):
        cloud_id = "123456"
        # create two application roles in the same portfolio, one of which has been provisioned
        ApplicationRoleFactory.create(
            user=user,
            cloud_id=cloud_id,
            application=ApplicationFactory.create(portfolio=portfolio),
        )
        ApplicationRoleFactory.create(
            user=user, application=ApplicationFactory.create(portfolio=portfolio)
        )
        existing_cloud_id = ApplicationRoles.get_cloud_id_for_user(
            user.dod_id, portfolio.id
        )
        assert existing_cloud_id == cloud_id

    def test_app_role_provisioned_new_portfolio(self, user, portfolio):
        cloud_id = "123456"
        # create two application roles in two different portfolios, one of which has been provisioned
        ApplicationRoleFactory.create(
            user=user,
            cloud_id=cloud_id,
            application=ApplicationFactory.create(portfolio=portfolio),
        )
        portfolio_2 = PortfolioFactory.create()
        ApplicationRoleFactory.create(
            user=user, application=ApplicationFactory.create(portfolio=portfolio_2)
        )
        assert (
            ApplicationRoles.get_cloud_id_for_user(user.dod_id, portfolio_2.id) is None
        )

    def test_no_application_roles(self, user, portfolio):
        assert ApplicationRoles.get_cloud_id_for_user(user.dod_id, portfolio.id) is None

    def test_app_role_not_provisioned(self, user, portfolio):
        ApplicationRoleFactory.create(
            user=user, application=ApplicationFactory.create(portfolio=portfolio)
        )
        assert ApplicationRoles.get_cloud_id_for_user(user.dod_id, portfolio.id) is None
