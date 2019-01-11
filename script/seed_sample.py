# Add root application dir to the python path
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

from atst.database import db
from atst.app import make_config, make_app
from atst.domain.users import Users
from atst.domain.requests import Requests
from atst.domain.portfolios import Portfolios
from atst.domain.applications import Applications
from atst.domain.portfolio_roles import PortfolioRoles
from atst.models.invitation import Status as InvitationStatus
from atst.domain.exceptions import AlreadyExistsError
from tests.factories import RequestFactory, LegacyTaskOrderFactory, InvitationFactory
from atst.routes.dev import _DEV_USERS as DEV_USERS

portfolio_USERS = [
    {
        "first_name": "Danny",
        "last_name": "Knight",
        "email": "knight@mil.gov",
        "portfolio_role": "developer",
        "dod_id": "0000000001",
    },
    {
        "first_name": "Mario",
        "last_name": "Hudson",
        "email": "hudson@mil.gov",
        "portfolio_role": "billing_auditor",
        "dod_id": "0000000002",
    },
    {
        "first_name": "Louise",
        "last_name": "Greer",
        "email": "greer@mil.gov",
        "portfolio_role": "admin",
        "dod_id": "0000000003",
    },
]

portfolio_INVITED_USERS = [
    {
        "first_name": "Frederick",
        "last_name": "Fitzgerald",
        "email": "frederick@mil.gov",
        "portfolio_role": "developer",
        "dod_id": "0000000004",
        "status": InvitationStatus.REJECTED_WRONG_USER
    },
    {
        "first_name": "Gina",
        "last_name": "Guzman",
        "email": "gina@mil.gov",
        "portfolio_role": "developer",
        "dod_id": "0000000005",
        "status": InvitationStatus.REJECTED_EXPIRED
    },
    {
        "first_name": "Hector",
        "last_name": "Harper",
        "email": "hector@mil.gov",
        "portfolio_role": "developer",
        "dod_id": "0000000006",
        "status": InvitationStatus.REVOKED
    },
    {
        "first_name": "Isabella",
        "last_name": "Ingram",
        "email": "isabella@mil.gov",
        "portfolio_role": "developer",
        "dod_id": "0000000007",
        "status": InvitationStatus.PENDING
    },
]


def seed_db():
    users = []
    for dev_user in DEV_USERS.values():
        try:
            user = Users.create(**dev_user)
        except AlreadyExistsError:
            user = Users.get_by_dod_id(dev_user["dod_id"])

        users.append(user)

    for user in users:
        if Requests.get_many(creator=user):
            continue

        requests = []
        for dollar_value in [1, 200, 3000, 40000, 500000, 1000000]:
            request = RequestFactory.build(creator=user)
            request.latest_revision.dollar_value = dollar_value
            db.session.add(request)
            db.session.commit()

            Requests.submit(request)
            requests.append(request)

        request = requests[0]
        request.legacy_task_order = LegacyTaskOrderFactory.build()
        request = Requests.update(
            request.id, {"financial_verification": RequestFactory.mock_financial_data()}
        )

        portfolio = Portfolios.create(
            user, name="{}'s portfolio".format(user.first_name)
        )
        for portfolio_role in portfolio_USERS:
            ws_role = Portfolios.create_member(user, portfolio, portfolio_role)
            db.session.refresh(ws_role)
            PortfolioRoles.enable(ws_role)

        for portfolio_role in portfolio_INVITED_USERS:
            ws_role = Portfolios.create_member(user, portfolio, portfolio_role)
            invitation = InvitationFactory.build(portfolio_role=ws_role, status=portfolio_role["status"])
            db.session.add(invitation)

        db.session.commit()

        Applications.create(
            user,
            portfolio=portfolio,
            name="First Application",
            description="This is our first application.",
            environment_names=["dev", "staging", "prod"],
        )


if __name__ == "__main__":
    config = make_config()
    app = make_app(config)
    with app.app_context():
        seed_db()
