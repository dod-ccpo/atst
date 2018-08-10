import pytest
from flask import session, url_for
from .mocks import DOD_SDN_INFO, DOD_SDN, FIXTURE_EMAIL_ADDRESS
from atst.domain.users import Users
from atst.domain.exceptions import NotFoundError
from .factories import UserFactory


MOCK_USER = {"id": "438567dd-25fa-4d83-a8cc-8aa8366cb24a"}


def _fetch_user_info(c, t):
    return MOCK_USER


def test_successful_login_redirect(client, monkeypatch):
    monkeypatch.setattr("atst.domain.authnid.AuthenticationContext.authenticate", lambda *args: True)
    monkeypatch.setattr("atst.domain.authnid.AuthenticationContext.get_user", lambda *args: UserFactory.create())

    resp = client.get(
        "/login-redirect",
        environ_base={
            "HTTP_X_SSL_CLIENT_VERIFY": "SUCCESS",
            "HTTP_X_SSL_CLIENT_S_DN": "",
            "HTTP_X_SSL_CLIENT_CERT": "",
        },
    )

    assert resp.status_code == 302
    assert "home" in resp.headers["Location"]
    assert session["user_id"]


def test_unsuccessful_login_redirect(client, monkeypatch):
    resp = client.get("/login-redirect")

    assert resp.status_code == 401
    assert "user_id" not in session


# checks that all of the routes in the app are protected by auth


def test_routes_are_protected(client, app):
    for rule in app.url_map.iter_rules():
        args = [1] * len(rule.arguments)
        mock_args = dict(zip(rule.arguments, args))
        _n, route = rule.build(mock_args)
        if route in UNPROTECTED_ROUTES or "/static" in route:
            continue

        if "GET" in rule.methods:
            resp = client.get(route)
            assert resp.status_code == 302
            assert resp.headers["Location"] == "http://localhost/"

        if "POST" in rule.methods:
            resp = client.post(route)
            assert resp.status_code == 302
            assert resp.headers["Location"] == "http://localhost/"


UNPROTECTED_ROUTES = ["/", "/login-dev", "/login-redirect", "/unauthorized"]
# this implicitly relies on the test config and test CRL in tests/fixtures/crl


def test_crl_validation_on_login(client):
    good_cert = open("ssl/client-certs/atat.mil.crt").read()
    bad_cert = open("ssl/client-certs/bad-atat.mil.crt").read()

    # bad cert is on the test CRL
    resp = client.get(
        "/login-redirect",
        environ_base={
            "HTTP_X_SSL_CLIENT_VERIFY": "SUCCESS",
            "HTTP_X_SSL_CLIENT_S_DN": DOD_SDN,
            "HTTP_X_SSL_CLIENT_CERT": bad_cert,
        },
    )
    assert resp.status_code == 401
    assert "user_id" not in session

    # good cert is not on the test CRL, passes
    resp = client.get(
        "/login-redirect",
        environ_base={
            "HTTP_X_SSL_CLIENT_VERIFY": "SUCCESS",
            "HTTP_X_SSL_CLIENT_S_DN": DOD_SDN,
            "HTTP_X_SSL_CLIENT_CERT": good_cert,
        },
    )
    assert resp.status_code == 302
    assert "home" in resp.headers["Location"]
    assert session["user_id"]


def test_creates_new_user_on_login(monkeypatch, client):
    monkeypatch.setattr("atst.domain.authnid.AuthenticationContext.authenticate", lambda *args: True)
    cert_file = open("tests/fixtures/{}.crt".format(FIXTURE_EMAIL_ADDRESS)).read()

    # ensure user does not exist
    with pytest.raises(NotFoundError):
        Users.get_by_dod_id(DOD_SDN_INFO["dod_id"])

    resp = client.get(
        "/login-redirect",
        environ_base={
            "HTTP_X_SSL_CLIENT_VERIFY": "SUCCESS",
            "HTTP_X_SSL_CLIENT_S_DN": DOD_SDN,
            "HTTP_X_SSL_CLIENT_CERT": cert_file,
        },
    )

    user = Users.get_by_dod_id(DOD_SDN_INFO["dod_id"])
    assert user.first_name == DOD_SDN_INFO["first_name"]
    assert user.last_name == DOD_SDN_INFO["last_name"]
    assert user.email == FIXTURE_EMAIL_ADDRESS


def test_creates_new_user_without_email_on_login(monkeypatch, client):
    monkeypatch.setattr("atst.routes._is_valid_certificate", lambda *args: True)
    cert_file = open("ssl/client-certs/atat.mil.crt").read()

    # ensure user does not exist
    with pytest.raises(NotFoundError):
        Users.get_by_dod_id(DOD_SDN_INFO["dod_id"])

    resp = client.get(
        "/login-redirect",
        environ_base={
            "HTTP_X_SSL_CLIENT_VERIFY": "SUCCESS",
            "HTTP_X_SSL_CLIENT_S_DN": DOD_SDN,
            "HTTP_X_SSL_CLIENT_CERT": cert_file,
        },
    )

    user = Users.get_by_dod_id(DOD_SDN_INFO["dod_id"])
    assert user.first_name == DOD_SDN_INFO["first_name"]
    assert user.last_name == DOD_SDN_INFO["last_name"]
    assert user.email == None
