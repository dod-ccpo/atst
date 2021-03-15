from unittest.mock import patch

import pytest

from atat.domain.environment_roles import EnvironmentRoles
from atat.models import ApplicationRoleStatus, EnvironmentRoleStatus
from tests.factories import (
    ApplicationFactory,
    ApplicationRoleFactory,
    EnvironmentFactory,
    EnvironmentRoleFactory,
    UserFactory,
    uuid4,
)


@pytest.fixture
def application_role():
    user = UserFactory.create()
    application = ApplicationFactory.create()
    return ApplicationRoleFactory.create(application=application, user=user)


@pytest.fixture
def environment(application_role):
    return EnvironmentFactory.create(application=application_role.application)


def test_create(application_role, environment, monkeypatch):
    environment_role = EnvironmentRoles.create(
        application_role, environment, "network admin"
    )
    assert environment_role.application_role == application_role
    assert environment_role.environment == environment
    assert environment_role.role == "network admin"


def test_get(application_role, environment):
    EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment
    )

    environment_role = EnvironmentRoles.get(application_role.id, environment.id)
    assert environment_role
    assert environment_role.application_role == application_role
    assert environment_role.environment == environment


def test_activate(application_role, environment):
    role = EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment
    )
    assert role.cloud_id is None
    assert role.status == EnvironmentRoleStatus.PENDING

    EnvironmentRoles.activate(role, "123")

    assert role.cloud_id == "123"
    assert role.status == EnvironmentRoleStatus.ACTIVE


def test_get_by_user_and_environment(application_role, environment):
    expected_role = EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment
    )
    actual_role = EnvironmentRoles.get_by_user_and_environment(
        application_role.user.id, environment.id
    )
    assert expected_role == actual_role


def test_delete(application_role, environment, monkeypatch):
    env_role = EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment
    )
    assert EnvironmentRoles.delete(application_role.id, environment.id)
    assert not EnvironmentRoles.delete(application_role.id, environment.id)


def test_get_for_application_member(application_role, environment):
    EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment
    )

    roles = EnvironmentRoles.get_for_application_member(application_role.id)
    assert len(roles) == 1
    assert roles[0].environment == environment
    assert roles[0].application_role == application_role


def test_get_for_application_member_does_not_return_deleted(
    application_role, environment
):
    EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment, deleted=True
    )

    roles = EnvironmentRoles.get_for_application_member(application_role.id)
    assert len(roles) == 0


class Test_disable:
    def test_completed(self, application_role, environment):
        environment_role = EnvironmentRoleFactory.create(
            application_role=application_role,
            environment=environment,
            status=EnvironmentRoleStatus.ACTIVE,
        )
        EnvironmentRoles.disable(environment_role.id)
        assert environment_role.is_disabled

    @patch("atat.domain.environment_roles.app.csp.cloud.disable_user")
    def test_has_cloud_id(self, disable_user, app):
        cloud_id = uuid4()
        env_role = EnvironmentRoleFactory.create(cloud_id=cloud_id)
        EnvironmentRoles.disable(env_role.id)
        assert disable_user.call_args == ((None, str(cloud_id)),)

    @patch("atat.domain.environment_roles.app.csp.cloud.disable_user")
    def test_no_cloud_id(self, disable_user):
        env_role = EnvironmentRoleFactory.create(cloud_id=None)
        EnvironmentRoles.disable(env_role.id)
        assert not disable_user.called


def test_get_for_update(application_role, environment):
    EnvironmentRoleFactory.create(
        application_role=application_role, environment=environment, deleted=True
    )
    role = EnvironmentRoles.get_for_update(application_role.id, environment.id)
    assert role
    assert role.application_role == application_role
    assert role.environment == environment
    assert role.deleted


def test_for_user(application_role):
    portfolio = application_role.application.portfolio
    user = application_role.user
    # create roles for 2 environments associated with application_role fixture
    env_role_1 = EnvironmentRoleFactory.create(application_role=application_role)
    env_role_2 = EnvironmentRoleFactory.create(application_role=application_role)

    # create role for environment in a different app in same portfolio
    application = ApplicationFactory.create(portfolio=portfolio)
    env_role_3 = EnvironmentRoleFactory.create(
        application_role=ApplicationRoleFactory.create(
            application=application, user=user
        )
    )

    # create role for environment for random user in app2
    rando_app_role = ApplicationRoleFactory.create(application=application)
    rando_env_role = EnvironmentRoleFactory.create(application_role=rando_app_role)

    env_roles = EnvironmentRoles.for_user(user.id, portfolio.id)
    assert len(env_roles) == 3
    assert set(env_roles) == {env_role_1, env_role_2, env_role_3}
    assert not rando_env_role in env_roles


class TestPendingCreation:
    def test_pending_role(self):
        appr = ApplicationRoleFactory.create(cloud_id="123")
        envr = EnvironmentRoleFactory.create(application_role=appr)
        assert EnvironmentRoles.get_pending_creation() == [envr.id]

    def test_deleted_role(self):
        appr = ApplicationRoleFactory.create(cloud_id="123")
        envr = EnvironmentRoleFactory.create(application_role=appr, deleted=True)
        assert EnvironmentRoles.get_pending_creation() == []

    def test_not_ready_role(self):
        appr = ApplicationRoleFactory.create(cloud_id=None)
        envr = EnvironmentRoleFactory.create(application_role=appr)
        assert EnvironmentRoles.get_pending_creation() == []

    def test_disabled_app_role(self):
        appr = ApplicationRoleFactory.create(
            cloud_id="123", status=ApplicationRoleStatus.DISABLED
        )
        envr = EnvironmentRoleFactory.create(application_role=appr)
        assert EnvironmentRoles.get_pending_creation() == []

    def test_disabled_env_role(self):
        appr = ApplicationRoleFactory.create(cloud_id="123")
        envr = EnvironmentRoleFactory.create(
            application_role=appr, status=EnvironmentRoleStatus.DISABLED
        )
        assert EnvironmentRoles.get_pending_creation() == []
