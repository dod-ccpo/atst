from typing import List
from uuid import UUID

from flask import g
from sqlalchemy import and_, func, or_

from atat.database import db
from atat.domain.application_roles import ApplicationRoles
from atat.domain.environments import Environments
from atat.domain.exceptions import NotFoundError
from atat.domain.invitations import ApplicationInvitations
from atat.models import (
    Application,
    ApplicationRole,
    ApplicationRoleStatus,
    EnvironmentRole,
    Portfolio,
    PortfolioStateMachine,
)
from atat.models.mixins.state_machines import PortfolioStates
from atat.utils import commit_or_raise_already_exists_error, first_or_none

from . import BaseDomainClass


class Applications(BaseDomainClass):
    model = Application
    resource_name = "application"

    @classmethod
    def create(cls, user, portfolio, name, description, environment_names=None):
        application = Application(
            portfolio=portfolio, name=name, description=description
        )
        db.session.add(application)

        if environment_names:
            Environments.create_many(user, application, environment_names)

        commit_or_raise_already_exists_error(message="application")
        return application

    @classmethod
    def for_user(cls, user, portfolio):
        return (
            db.session.query(Application)
            .join(ApplicationRole)
            .filter(Application.portfolio_id == portfolio.id)
            .filter(ApplicationRole.application_id == Application.id)
            .filter(ApplicationRole.user_id == user.id)
            .filter(ApplicationRole.status == ApplicationRoleStatus.ACTIVE)
            .all()
        )

    @classmethod
    def update(cls, application, new_data):
        if "name" in new_data:
            application.name = new_data["name"]
        if "description" in new_data:
            application.description = new_data["description"]
        if "environment_names" in new_data:
            Environments.create_many(
                g.current_user, application, new_data["environment_names"]
            )

        db.session.add(application)
        commit_or_raise_already_exists_error(message="application")
        return application

    @classmethod
    def delete(cls, application):
        for env in application.environments:
            Environments.delete(env)

        application.deleted = True

        for role in application.roles:
            role.deleted = True
            role.status = ApplicationRoleStatus.DISABLED
            db.session.add(role)

        db.session.add(application)
        db.session.commit()

    @classmethod
    def invite(
        cls,
        application,
        inviter,
        user_data,
        permission_sets_names=None,
        environment_roles_data=[],
        cloud_id=None,
    ):
        permission_sets_names = permission_sets_names or []
        permission_sets = ApplicationRoles._permission_sets_for_names(
            permission_sets_names
        )
        app_role = ApplicationRole(
            application=application, permission_sets=permission_sets, cloud_id=cloud_id,
        )

        db.session.add(app_role)

        for env_role_data in environment_roles_data:
            env_role_name = env_role_data.get("role")
            environment_id = env_role_data.get("environment_id")
            if env_role_name is not None:
                # pylint: disable=cell-var-from-loop
                environment = first_or_none(
                    lambda e, env_id=environment_id: str(e.id) == str(env_id),
                    application.environments,
                )
                if environment is None:
                    raise NotFoundError("environment")
                else:
                    env_role = EnvironmentRole(
                        application_role=app_role,
                        environment=environment,
                        role=env_role_name,
                    )
                    db.session.add(env_role)

        invitation = ApplicationInvitations.create(
            inviter=inviter, role=app_role, member_data=user_data
        )
        db.session.add(invitation)

        db.session.commit()

        return invitation

    @classmethod
    def get_applications_pending_creation(cls) -> List[UUID]:
        results = (
            db.session.query(Application.id)
            .join(Portfolio)
            .join(PortfolioStateMachine)
            .filter(
                and_(
                    PortfolioStateMachine.state == PortfolioStates.COMPLETED,
                    Application.deleted == False,
                    Application.cloud_id.is_(None),
                    or_(
                        Application.claimed_until.is_(None),
                        Application.claimed_until <= func.now(),
                    ),
                )
            )
        ).all()
        return [id_ for id_, in results]
