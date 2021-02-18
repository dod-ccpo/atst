import os
from datetime import datetime
from unittest.mock import Mock
from urllib.parse import quote, urlparse

import pendulum
import pytest
from flask import session, url_for

from atat.domain.auth import UNPROTECTED_ROUTES
from atat.domain.exceptions import NotFoundError
from atat.domain.users import Users
from tests.factories import UserFactory
from tests.utils import FakeLogger

PROTECTED_URL = "/home"


def test_home_page_with_complete_profile(client, user_session):
    user = UserFactory.create()
    user_session(user)
    response = client.get(PROTECTED_URL, follow_redirects=False)
    assert response.status_code == 200


def test_redirect_when_profile_missing_fields(client, user_session):
    user = UserFactory.create(email=None)
    user_session(user)
    response = client.get(PROTECTED_URL, follow_redirects=False)
    assert response.status_code == 302
    assert "/user?next={}".format(quote(PROTECTED_URL, safe="")) in response.location


def test_completing_user_profile(client, user_session):
    user = UserFactory.create(phone_number=None)
    user_session(user)
    response = client.get(PROTECTED_URL, follow_redirects=True)
    assert b"You must complete your profile" in response.data

    updated_data = {**user.to_dictionary(), "phone_number": "5558675309"}
    response = client.post(url_for("users.update_user"), data=updated_data)
    assert response.status_code == 200

    response = client.get(PROTECTED_URL, follow_redirects=False)
    assert response.status_code == 200
    assert b"You must complete your profile" not in response.data


@pytest.fixture
def mock_login(monkeypatch):
    def _mock_login(user, client, **kwargs):
        monkeypatch.setattr(
            "atat.routes.load_attributes_from_assertion", lambda *a: None
        )
        monkeypatch.setattr(
            "atat.routes.get_user_from_saml_attributes", lambda *a: user
        )
        return client.post(url_for("atat.login", acs=""))

    return _mock_login


# checks that all of the routes in the app are protected by auth
def is_unprotected(rule):
    return rule.endpoint in UNPROTECTED_ROUTES


def protected_routes(app):
    for rule in app.url_map.iter_rules():
        args = [1] * len(rule.arguments)
        mock_args = dict(zip(rule.arguments, args))
        _n, route = rule.build(mock_args)
        if is_unprotected(rule) or "/static" in route:
            continue
        yield rule, route


def test_protected_routes_redirect_to_login(client, app):
    server_name = app.config.get("SERVER_NAME") or "localhost"
    for rule, protected_route in protected_routes(app):
        if "GET" in rule.methods:
            resp = client.get(protected_route)
            assert resp.status_code == 302
            assert server_name in resp.headers["Location"]

        if "POST" in rule.methods:
            resp = client.post(protected_route)
            assert resp.status_code == 302
            assert server_name in resp.headers["Location"]


def test_logout(app, client, mock_login, mock_logger):
    user = UserFactory.create()
    # create a real session
    mock_login(user, client)
    resp_success = client.get(url_for("users.user"))
    # verify session is valid
    assert resp_success.status_code == 200
    client.get(url_for("atat.logout"))
    resp_failure = client.get(url_for("users.user"))
    # verify that logging out has cleared the session
    assert resp_failure.status_code == 302
    destination = urlparse(resp_failure.headers["Location"]).path
    assert destination == url_for("atat.root")
    # verify that logout is noted in the logs
    logout_msg = mock_logger.messages[-1]
    assert user.dod_id in logout_msg
    assert "logged out" in logout_msg


def test_logging_out_creates_a_flash_message(app, client, mock_login):
    user = UserFactory.create()
    mock_login(user, client)
    logout_response = client.get(url_for("atat.logout"), follow_redirects=True)

    assert "Logged out" in logout_response.data.decode()


def test_redirected_on_login(client, monkeypatch, mock_login):
    target_route = url_for("users.user")
    user = UserFactory.create()
    # create a mock for the SAML provider
    saml_auth_mock = Mock()
    # mock our the last request ID, which must be serialized to the session
    saml_auth_mock.get_last_request_id.return_value = 5
    monkeypatch.setattr(
        "atat.routes.saml_helpers.init_saml_auth", lambda *a: saml_auth_mock
    )
    # GET the login route, which will populate the "next" param in the user's session
    response = client.get(url_for("atat.login", next=target_route))
    # login with the POST portion of the fed auth flow; user should be
    # redirected to the location of the original "next" param
    response = mock_login(user, client)
    assert response.status_code == 302
    assert target_route in response.headers.get("Location")


def test_last_login_set_when_user_logs_in(client, mock_login):
    last_login = pendulum.now(tz="UTC")
    user = UserFactory.create(last_login=last_login)
    mock_login(user, client)
    assert session["last_login"]
    assert user.last_login > session["last_login"]
    assert isinstance(session["last_login"], datetime)


@pytest.mark.parametrize(
    "url,status_code", [("/", 200), ("/this-page-will-never-exist", 302)]
)
def test_hsts_unprotected(client, url, status_code):
    response = client.get(url, follow_redirects=False)
    assert response.status_code == status_code
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains; always"
    )


@pytest.mark.parametrize(
    "url,status_code", [(PROTECTED_URL, 200), ("/this-page-will-never-exist", 404)]
)
def test_hsts_protected(client, mock_login, url, status_code):
    user = UserFactory.create()
    mock_login(user, client)
    response = client.get(url, follow_redirects=False)
    assert response.status_code == status_code
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains; always"
    )
