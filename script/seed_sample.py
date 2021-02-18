# Add root application dir to the python path
import os
import sys
import pendulum
import random
from faker import Faker
from werkzeug.datastructures import FileStorage
from uuid import uuid4

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

from atat.app import make_config, make_app
from atat.database import db

from atat.models.application import Application
from atat.models.clin import JEDICLINType
from atat.models.environment_role import CSPRole

from atat.domain.application_roles import ApplicationRoles
from atat.domain.applications import Applications
from atat.domain.csp.reports import MockReportingProvider
from atat.domain.environments import Environments
from atat.domain.environment_roles import EnvironmentRoles
from atat.domain.exceptions import AlreadyExistsError, NotFoundError
from atat.domain.invitations import ApplicationInvitations
from atat.domain.permission_sets import PermissionSets, APPLICATION_PERMISSION_SETS
from atat.domain.portfolio_roles import PortfolioRoles
from atat.domain.portfolios import Portfolios
from atat.domain.users import Users

from atat.routes.dev import _DEV_USERS as DEV_USERS

from atat.utils import pick

from tests.factories import (
    random_defense_component,
    TaskOrderFactory,
    CLINFactory,
    AttachmentFactory,
)

fake = Faker()


PORTFOLIO_USERS = [
    {
        "first_name": "Danny",
        "last_name": "Knight",
        "email": "knight@mil.gov",
        "dod_id": "0000000001",
        "permission_sets": PortfolioRoles.DEFAULT_PORTFOLIO_PERMISSION_SETS,
    },
    {
        "first_name": "Mario",
        "last_name": "Hudson",
        "email": "hudson@mil.gov",
        "dod_id": "0000000002",
        "permission_sets": PortfolioRoles.DEFAULT_PORTFOLIO_PERMISSION_SETS,
    },
    {
        "first_name": "Louise",
        "last_name": "Greer",
        "email": "greer@mil.gov",
        "dod_id": "0000000003",
        "permission_sets": PortfolioRoles.DEFAULT_PORTFOLIO_PERMISSION_SETS,
    },
]


APPLICATION_USERS = [
    {
        "first_name": "Jean Luc",
        "last_name": "Picard",
        "email": "picard@mil.gov",
        "dod_id": "0000000004",
        "permission_sets": random.sample(
            APPLICATION_PERMISSION_SETS, k=random.randint(1, 4)
        ),
    },
    {
        "first_name": "()",
        "last_name": "Spock",
        "email": "spock@mil.gov",
        "dod_id": "0000000005",
        "permission_sets": random.sample(
            APPLICATION_PERMISSION_SETS, k=random.randint(1, 4)
        ),
    },
    {
        "first_name": "William",
        "last_name": "Shatner",
        "email": "shatner@mil.gov",
        "dod_id": "0000000006",
        "permission_sets": random.sample(
            APPLICATION_PERMISSION_SETS, k=random.randint(1, 4)
        ),
    },
    {
        "first_name": "Nyota",
        "last_name": "Uhura",
        "email": "uhura@mil.gov",
        "dod_id": "0000000007",
        "permission_sets": random.sample(
            APPLICATION_PERMISSION_SETS, k=random.randint(1, 4)
        ),
    },
    {
        "first_name": "Kathryn",
        "last_name": "Janeway",
        "email": "janeway@mil.gov",
        "dod_id": "0000000008",
        "permission_sets": random.sample(
            APPLICATION_PERMISSION_SETS, k=random.randint(1, 4)
        ),
    },
]


SHIP_NAMES = [
    "Millenium Falcon",
    "Star Destroyer",
    "Attack Cruiser",
    "Sith Infiltrator",
    "Death Star",
    "Lambda Shuttle",
    "Corellian Corvette",
]


SOFTWARE_WORDS = [
    "Enterprise",
    "Scalable",
    "Solution",
    "Blockchain",
    "Cloud",
    "Micro",
    "Macro",
    "Software",
    "Global",
    "Team",
]


ENVIRONMENT_NAMES = ["production", "staging", "test", "uat", "dev", "qa"]


def get_users():
    users = []
    for dev_user in DEV_USERS.values():
        try:
            user = Users.create(**dev_user)
        except AlreadyExistsError:
            user = Users.get_by_dod_id(dev_user["dod_id"])

        users.append(user)
    return users


def add_members_to_portfolio(portfolio):
    for user_data in PORTFOLIO_USERS:
        invite = Portfolios.invite(portfolio, portfolio.owner, {"user_data": user_data})
        profile = {
            k: user_data[k] for k in user_data if k not in ["dod_id", "permission_sets"]
        }
        user = Users.get_or_create_by_dod_id(user_data["dod_id"], **profile)
        PortfolioRoles.enable(invite.role, user)

    db.session.commit()


def add_task_orders_to_portfolio(portfolio):
    today = pendulum.today(tz="UTC")
    future = today.add(days=100)
    yesterday = today.subtract(days=1)

    def build_pdf():
        return {"filename": "sample_task_order.pdf", "object_name": str(uuid4())}

    draft_to = TaskOrderFactory.build(portfolio=portfolio, pdf=None)
    unsigned_to = TaskOrderFactory.build(portfolio=portfolio, pdf=build_pdf())
    upcoming_to = TaskOrderFactory.build(
        portfolio=portfolio, signed_at=yesterday, pdf=build_pdf()
    )
    expired_to = TaskOrderFactory.build(
        portfolio=portfolio, signed_at=yesterday, pdf=build_pdf()
    )
    active_to = TaskOrderFactory.build(
        portfolio=portfolio, signed_at=yesterday, pdf=build_pdf()
    )

    clins = [
        CLINFactory.build(
            task_order=unsigned_to, start_date=today.subtract(days=5), end_date=today
        ),
        CLINFactory.build(
            task_order=upcoming_to, start_date=today.add(days=5), end_date=future
        ),
        CLINFactory.build(
            task_order=expired_to, start_date=today.subtract(days=5), end_date=yesterday
        ),
        CLINFactory.build(
            task_order=active_to,
            start_date=yesterday,
            end_date=future,
            total_amount=1_000_000,
            obligated_amount=500_000,
            jedi_clin_type=JEDICLINType.JEDI_CLIN_1,
        ),
        CLINFactory.build(
            task_order=active_to,
            start_date=yesterday,
            end_date=future,
            total_amount=500_000,
            obligated_amount=200_000,
            jedi_clin_type=JEDICLINType.JEDI_CLIN_2,
        ),
    ]

    task_orders = [draft_to, unsigned_to, upcoming_to, expired_to, active_to]

    db.session.add_all(task_orders + clins)
    db.session.commit()


def random_applications():
    return [
        {
            "name": fake.sentence(nb_words=3, ext_word_list=SOFTWARE_WORDS)[0:-1],
            "description": fake.bs(),
            "environments": random.sample(ENVIRONMENT_NAMES, k=random.randint(1, 4)),
        }
        for _ in range(random.randint(1, 4))
    ]


def add_applications_to_portfolio(portfolio):
    applications = random_applications()
    for application_data in applications:
        application = Applications.create(
            portfolio.owner,
            portfolio=portfolio,
            name=application_data["name"],
            description=application_data["description"],
            environment_names=application_data["environments"],
        )

        users = random.sample(APPLICATION_USERS, k=random.randint(1, 5))
        for user_data in users:
            try:
                user = Users.get_by_dod_id(user_data["dod_id"])
            except NotFoundError:
                user = Users.create(
                    user_data["dod_id"],
                    None,
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    email=user_data["email"],
                )

            app_role = ApplicationRoles.create(
                user=user,
                application=application,
                permission_set_names=[PermissionSets.EDIT_APPLICATION_TEAM],
            )

            ApplicationInvitations.create(
                portfolio.owner, app_role, user_data, commit=True
            )

            user_environments = random.sample(
                application.environments,
                k=random.randint(1, len(application.environments)),
            )
            for env in user_environments:
                role = random.choice([e.value for e in CSPRole])
                EnvironmentRoles.create(
                    application_role=app_role, environment=env, role=role
                )


def create_demo_portfolio(name, data):
    try:
        portfolio_owner = Users.get_or_create_by_dod_id(
            "2345678901",
            **pick(
                [
                    "permission_sets",
                    "first_name",
                    "last_name",
                    "email",
                    "service_branch",
                    "phone_number",
                    "citizenship",
                    "designation",
                ],
                DEV_USERS["amanda"],
            ),
        )  # Amanda
    except NotFoundError:
        print(
            "Could not find demo users; will not create demo portfolio {}".format(name)
        )
        return

    portfolio = Portfolios.create(
        user=portfolio_owner,
        portfolio_attrs={"name": name, "defense_component": random_defense_component()},
    )

    add_task_orders_to_portfolio(portfolio)
    add_members_to_portfolio(portfolio)

    for mock_application in data["applications"]:
        application = Application(
            portfolio=portfolio, name=mock_application["name"], description=""
        )
        env_names = [env["name"] for env in mock_application["environments"]]
        Environments.create_many(portfolio.owner, application, env_names)
        db.session.add(application)
        db.session.commit()


def seed_db():
    get_users()
    amanda = Users.get_by_dod_id("2345678901")

    # Create Portfolios for Amanda with mocked reporting data
    create_demo_portfolio("A-Wing", MockReportingProvider.FIXTURE_SPEND_DATA["A-Wing"])
    create_demo_portfolio("B-Wing", MockReportingProvider.FIXTURE_SPEND_DATA["B-Wing"])

    tie_interceptor = Portfolios.create(
        user=amanda,
        portfolio_attrs={
            "name": "TIE Interceptor",
            "defense_component": random_defense_component(),
        },
    )
    add_task_orders_to_portfolio(tie_interceptor)
    add_members_to_portfolio(tie_interceptor)
    add_applications_to_portfolio(tie_interceptor)

    tie_fighter = Portfolios.create(
        user=amanda,
        portfolio_attrs={
            "name": "TIE Fighter",
            "defense_component": random_defense_component(),
        },
    )
    add_task_orders_to_portfolio(tie_fighter)
    add_members_to_portfolio(tie_fighter)
    add_applications_to_portfolio(tie_fighter)

    # create a portfolio for each user
    ships = SHIP_NAMES.copy()
    for user in get_users():
        ship = random.choice(ships)
        ships.remove(ship)
        portfolio = Portfolios.create(
            user=user,
            portfolio_attrs={
                "name": ship,
                "defense_component": random_defense_component(),
            },
        )
        add_task_orders_to_portfolio(portfolio)
        add_members_to_portfolio(portfolio)
        add_applications_to_portfolio(portfolio)


if __name__ == "__main__":
    config = make_config({"default": {"DEBUG": False}})
    app = make_app(config)
    with app.app_context():
        seed_db()
