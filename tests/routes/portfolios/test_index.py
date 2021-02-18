import pytest
from flask import url_for

from atat.domain.portfolios import PortfolioDeletionApplicationsExistError, Portfolios
from atat.domain.portfolios.query import PortfoliosQuery
from atat.utils.localization import translate
from tests.factories import (
    ApplicationFactory,
    PortfolioFactory,
    TaskOrderFactory,
    UserFactory,
    random_future_date,
    random_past_date,
)


def test_new_portfolio(client, user_session):
    user = UserFactory.create()
    user_session(user)

    response = client.get(url_for("portfolios.new_portfolio_step_1"))

    assert response.status_code == 200


def test_create_portfolio_success(client, user_session):
    user = UserFactory.create()
    user_session(user)

    original_portfolio_count = len(PortfoliosQuery.get_all())

    response = client.post(
        url_for("portfolios.create_portfolio"),
        data={
            "name": "My project name",
            "description": "My project description",
            "defense_component": ["army"],
        },
    )

    assert response.status_code == 302
    assert len(PortfoliosQuery.get_all()) == original_portfolio_count + 1

    new_portfolio = Portfolios.for_user(user=user)[-1]

    assert (
        url_for("task_orders.portfolio_funding", portfolio_id=new_portfolio.id)
        in response.location
    )
    assert new_portfolio.owner == user


def test_create_portfolio_failure(client, user_session):
    user = UserFactory.create()
    user_session(user)

    original_portfolio_count = len(PortfoliosQuery.get_all())

    response = client.post(
        url_for("portfolios.create_portfolio"),
        data={"name": "My project name", "description": "My project description"},
    )

    assert response.status_code == 400
    assert len(PortfoliosQuery.get_all()) == original_portfolio_count


def test_portfolio_reports(client, user_session):
    portfolio = PortfolioFactory.create(
        applications=[
            {"name": "application1", "environments": [{"name": "application1 prod"}]}
        ]
    )
    task_order = TaskOrderFactory.create(number="42", portfolio=portfolio)
    user_session(portfolio.owner)
    response = client.get(url_for("portfolios.reports", portfolio_id=portfolio.id))
    assert response.status_code == 200
    assert portfolio.name in response.data.decode()


def test_portfolio_reports_with_mock_portfolio(client, user_session):
    portfolio = PortfolioFactory.create(name="A-Wing")
    user_session(portfolio.owner)
    response = client.get(url_for("portfolios.reports", portfolio_id=portfolio.id))
    assert response.status_code == 200
    assert portfolio.name in response.data.decode()
