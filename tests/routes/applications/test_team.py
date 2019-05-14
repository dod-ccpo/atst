import pytest
import uuid
from flask import url_for

from atst.domain.permission_sets import PermissionSets
from atst.models import CSPRole

from tests.factories import *


def test_application_team(client, user_session):
    portfolio = PortfolioFactory.create()
    application = ApplicationFactory.create(portfolio=portfolio)

    user_session(portfolio.owner)

    response = client.get(url_for("applications.team", application_id=application.id))
    assert response.status_code == 200


def test_update_team_permissions(client, user_session):
    application = ApplicationFactory.create()
    owner = application.portfolio.owner
    app_role = ApplicationRoleFactory.create(
        application=application, permission_sets=[]
    )
    app_user = app_role.user
    user_session(owner)
    response = client.post(
        url_for("applications.update_team", application_id=application.id),
        data={
            "members-0-user_id": app_user.id,
            "members-0-permission_sets-perms_team_mgmt": PermissionSets.EDIT_APPLICATION_TEAM,
            "members-0-permission_sets-perms_env_mgmt": PermissionSets.EDIT_APPLICATION_ENVIRONMENTS,
            "members-0-permission_sets-perms_del_env": PermissionSets.DELETE_APPLICATION_ENVIRONMENTS,
        },
    )

    assert response.status_code == 302
    actual_perms_names = [perm.name for perm in app_role.permission_sets]
    expected_perms_names = [
        PermissionSets.VIEW_APPLICATION,
        PermissionSets.EDIT_APPLICATION_TEAM,
        PermissionSets.EDIT_APPLICATION_ENVIRONMENTS,
        PermissionSets.DELETE_APPLICATION_ENVIRONMENTS,
    ]
    assert expected_perms_names == actual_perms_names


def test_update_team_with_bad_permission_sets(client, user_session):
    application = ApplicationFactory.create()
    owner = application.portfolio.owner
    app_role = ApplicationRoleFactory.create(
        application=application, permission_sets=[]
    )
    app_user = app_role.user
    permission_sets = app_user.permission_sets

    user_session(owner)
    response = client.post(
        url_for("applications.update_team", application_id=application.id),
        data={
            "members-0-user_id": app_user.id,
            "members-0-permission_sets-perms_team_mgmt": PermissionSets.EDIT_APPLICATION_TEAM,
            "members-0-permission_sets-perms_env_mgmt": "some random string",
        },
    )
    assert response.status_code == 400
    assert app_user.permission_sets == permission_sets


def test_update_team_with_non_app_user(client, user_session):
    application = ApplicationFactory.create()
    owner = application.portfolio.owner
    app_role = ApplicationRoleFactory.create(
        application=application, permission_sets=[]
    )
    non_app_user = UserFactory.create()
    app_user = app_role.user

    user_session(owner)
    response = client.post(
        url_for("applications.update_team", application_id=application.id),
        data={
            "members-0-user_id": non_app_user.id,
            "members-0-permission_sets-perms_team_mgmt": PermissionSets.EDIT_APPLICATION_TEAM,
            "members-0-permission_sets-perms_env_mgmt": PermissionSets.EDIT_APPLICATION_ENVIRONMENTS,
            "members-0-permission_sets-perms_del_env": PermissionSets.DELETE_APPLICATION_ENVIRONMENTS,
        },
    )

    assert response.status_code == 404


def test_update_team_environment_roles(client, user_session):
    application = ApplicationFactory.create()
    owner = application.portfolio.owner
    app_role = ApplicationRoleFactory.create(
        application=application, permission_sets=[]
    )
    app_user = app_role.user
    environment = EnvironmentFactory.create(application=application)
    env_role = EnvironmentRoleFactory.create(
        user=app_user, environment=environment, role=CSPRole.NETWORK_ADMIN.value
    )
    user_session(owner)
    response = client.post(
        url_for("applications.update_team", application_id=application.id),
        data={
            "members-0-user_id": app_user.id,
            "members-0-permission_sets-perms_team_mgmt": PermissionSets.EDIT_APPLICATION_TEAM,
            "members-0-permission_sets-perms_env_mgmt": PermissionSets.EDIT_APPLICATION_ENVIRONMENTS,
            "members-0-permission_sets-perms_del_env": PermissionSets.DELETE_APPLICATION_ENVIRONMENTS,
            "members-0-environment_roles-0-environment_id": environment.id,
            "members-0-environment_roles-0-role": CSPRole.TECHNICAL_READ.value,
        },
    )

    assert response.status_code == 302
    assert env_role.role == CSPRole.TECHNICAL_READ.value


@pytest.mark.skip(reason="Need to rebase against master")
def test_update_team_revoke_environment_access(client, user_session):
    application = ApplicationFactory.create()
    owner = application.portfolio.owner
    app_role = ApplicationRoleFactory.create(
        application=application, permission_sets=[]
    )
    app_user = app_role.user
    environment = EnvironmentFactory.create(application=application)
    env_role = EnvironmentRoleFactory.create(
        user=app_user, environment=environment, role=CSPRole.BASIC_ACCESS.value
    )
    user_session(owner)
    response = client.post(
        url_for("applications.update_team", application_id=application.id),
        data={
            "members-0-user_id": app_user.id,
            "members-0-permission_sets-perms_team_mgmt": PermissionSets.EDIT_APPLICATION_TEAM,
            "members-0-permission_sets-perms_env_mgmt": PermissionSets.EDIT_APPLICATION_ENVIRONMENTS,
            "members-0-permission_sets-perms_del_env": PermissionSets.DELETE_APPLICATION_ENVIRONMENTS,
            "members-0-environment_roles-0-environment_id": environment.id,
            "members-0-environment_roles-0-role": "",
        },
    )

    assert response.status_code == 302
    assert env_role.role == CSPRole.TECHNICAL_READ.value


def test_create_member(client, user_session):
    user = UserFactory.create()
    application = ApplicationFactory.create(
        environments=[{"name": "Naboo"}, {"name": "Endor"}]
    )
    env = application.environments[0]

    user_session(application.portfolio.owner)

    response = client.post(
        url_for("applications.create_member", application_id=application.id),
        data={
            "user_data-first_name": user.first_name,
            "user_data-last_name": user.last_name,
            "user_data-dod_id": user.dod_id,
            "user_data-email": user.email,
            "environment_roles-0-environment_id": env.id,
            "environment_roles-0-environment_name": env.name,
            "environment_roles-0-role": "Basic Access",
            "permission_sets-perms_env_mgmt": True,
            "permission_sets-perms_team_mgmt": True,
            "permission_sets-perms_del_env": True,
        },
    )

    assert response.status_code == 302
    expected_url = url_for(
        "applications.team",
        application_id=application.id,
        fragment="application-members",
        _anchor="application-members",
        _external=True,
    )
    assert response.location == expected_url
    assert len(user.application_roles) == 1
    assert user.application_roles[0].application == application
    assert len(user.environment_roles) == 1
    assert user.environment_roles[0].environment == env


def test_remove_member_success(client, user_session):
    user = UserFactory.create()
    application = ApplicationFactory.create()
    application_role = ApplicationRoleFactory.create(application=application, user=user)

    user_session(application.portfolio.owner)

    response = client.post(
        url_for(
            "applications.remove_member", application_id=application.id, user_id=user.id
        )
    )

    assert response.status_code == 302
    assert response.location == url_for(
        "applications.team",
        _anchor="application-members",
        _external=True,
        application_id=application.id,
        fragment="application-members",
    )


def test_remove_member_failure(client, user_session):
    user = UserFactory.create()
    application = ApplicationFactory.create()

    user_session(application.portfolio.owner)

    response = client.post(
        url_for(
            "applications.remove_member",
            application_id=application.id,
            user_id=uuid.uuid4(),
        )
    )

    assert response.status_code == 404
