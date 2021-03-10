import pendulum
import pytest

from atat.domain.environment_roles import EnvironmentRoles
from atat.domain.permission_sets import PermissionSets
from atat.models.audit_event import AuditEvent
from tests.factories import *


@pytest.mark.audit_log
def test_has_application_role_history(session):
    owner = UserFactory.create()
    user = UserFactory.create()

    PortfolioFactory.create(
        owner=owner,
        applications=[
            {
                "name": "starkiller",
                "environments": [
                    {
                        "name": "bridge",
                        "members": [{"user": user, "role_name": "developer"}],
                    }
                ],
            }
        ],
    )

    app_role = user.application_roles[0]
    app_role.permission_sets = [
        PermissionSets.get(PermissionSets.EDIT_APPLICATION_TEAM)
    ]
    session.add(app_role)
    session.commit()

    changed_event = (
        session.query(AuditEvent)
        .filter(AuditEvent.resource_id == app_role.id, AuditEvent.action == "update")
        .one()
    )
    old_state, new_state = changed_event.changed_state["permission_sets"]
    assert old_state == [PermissionSets.VIEW_APPLICATION]
    assert new_state == [PermissionSets.EDIT_APPLICATION_TEAM]


def test_environment_roles():
    application = ApplicationFactory.create()
    environment1 = EnvironmentFactory.create(application=application)
    environment2 = EnvironmentFactory.create(application=application)
    user = UserFactory.create()
    application_role = ApplicationRoleFactory.create(application=application, user=user)
    environment_role1 = EnvironmentRoleFactory.create(
        environment=environment1, application_role=application_role
    )
    EnvironmentRoleFactory.create(
        environment=environment2, application_role=application_role, deleted=True
    )

    assert not EnvironmentRoles.get_by_user_and_environment(user.id, environment2.id)


class Test_display_status:
    def test_expired_invite(self):
        yesterday = pendulum.today(tz="UTC").subtract(days=1)
        expired_invite = ApplicationInvitationFactory.create(expiration_time=yesterday)
        assert expired_invite.role.display_status == "invite_expired"

    def test_invite_pending(self):
        app_role_pending = ApplicationRoleFactory.create()
        ApplicationInvitationFactory.create(
            role=app_role_pending, user=app_role_pending.user
        )
        assert app_role_pending.display_status == "invite_pending"

    def test_changes_pending(self):
        app_role_active = ApplicationRoleFactory.create(
            status=ApplicationRoleStatus.ACTIVE
        )
        env_role_pending = EnvironmentRoleFactory.create(
            application_role=app_role_active
        )
        assert env_role_pending.application_role.display_status == "changes_pending"

    def test_invite_accepted_no_environments(self):
        app_role_active = ApplicationRoleFactory.create(
            status=ApplicationRoleStatus.ACTIVE
        )
        assert app_role_active.display_status is None

    def test_invite_accepted_some_environments_pending(self):
        app_role_active = ApplicationRoleFactory.create(
            status=ApplicationRoleStatus.ACTIVE
        )
        EnvironmentRoleFactory.create(
            application_role=app_role_active, status=EnvironmentRoleStatus.PENDING
        )
        EnvironmentRoleFactory.create(
            application_role=app_role_active, status=EnvironmentRoleStatus.ACTIVE
        )
        assert app_role_active.display_status == "changes_pending"

    def test_invite_accepted_all_environments_completed(self):
        app_role_active = ApplicationRoleFactory.create(
            status=ApplicationRoleStatus.ACTIVE
        )
        EnvironmentRoleFactory.create(
            application_role=app_role_active, status=EnvironmentRoleStatus.ACTIVE
        )
        EnvironmentRoleFactory.create(
            application_role=app_role_active, status=EnvironmentRoleStatus.ACTIVE
        )
        assert app_role_active.display_status is None
