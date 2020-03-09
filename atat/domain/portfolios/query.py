from sqlalchemy import or_
from atat.database import db
from atat.domain.common import Query
from atat.models.portfolio import Portfolio
from atat.models.portfolio_role import PortfolioRole, Status as PortfolioRoleStatus
from atat.models.application_role import (
    ApplicationRole,
    Status as ApplicationRoleStatus,
)
from atat.models.application import Application
from atat.models.portfolio_state_machine import PortfolioStateMachine

# from atat.models.application import Application


class PortfolioStateMachinesQuery(Query):
    model = PortfolioStateMachine


class PortfoliosQuery(Query):
    model = Portfolio

    @classmethod
    def get_for_user(cls, user):
        return (
            db.session.query(Portfolio)
            .filter(
                or_(
                    Portfolio.id.in_(
                        db.session.query(Portfolio.id)
                        .join(Application)
                        .filter(Portfolio.id == Application.portfolio_id)
                        .filter(
                            Application.id.in_(
                                db.session.query(Application.id)
                                .join(ApplicationRole)
                                .filter(
                                    ApplicationRole.application_id == Application.id
                                )
                                .filter(ApplicationRole.user_id == user.id)
                                .filter(
                                    ApplicationRole.status
                                    == ApplicationRoleStatus.ACTIVE
                                )
                                .filter(ApplicationRole.deleted == False)
                                .subquery()
                            )
                        )
                    ),
                    Portfolio.id.in_(
                        db.session.query(Portfolio.id)
                        .join(PortfolioRole)
                        .filter(PortfolioRole.user == user)
                        .filter(PortfolioRole.status == PortfolioRoleStatus.ACTIVE)
                        .subquery()
                    ),
                )
            )
            .filter(Portfolio.deleted == False)
            .order_by(Portfolio.name.asc())
            .all()
        )

    @classmethod
    def create_portfolio_role(cls, user, portfolio, **kwargs):
        return PortfolioRole(user=user, portfolio=portfolio, **kwargs)