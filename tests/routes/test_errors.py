import pytest
from flask import url_for

from atat.app import make_app, make_config
from tests.factories import UserFactory


@pytest.fixture
def csrf_enabled_app(app):
    app.config.update({"WTF_CSRF_ENABLED": True})
    yield app
    app.config.update({"WTF_CSRF_ENABLED": False})


def test_csrf_error(csrf_enabled_app, client):
    response = client.post(
        url_for("users.user"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data="csrf_token=invalid_token",
        follow_redirects=True,
    )

    body = response.data.decode()
    assert "Session Expired" in body
    assert "Login required" in body


@pytest.fixture
def blowup_app(notification_sender):
    _blowup_app = make_app(make_config(direct_config={"default": {"DEBUG": False}}))
    _blowup_app.notification_sender = notification_sender

    @_blowup_app.route("/throw")
    def throw():
        raise ValueError()

    yield _blowup_app


@pytest.fixture
def blowup_client(blowup_app):
    yield blowup_app.test_client()


def test_errors_generate_notifications(
    blowup_client, client, user_session, notification_sender
):
    user_session(UserFactory.create())

    blowup_client.get("/throw")

    notification_sender.send.assert_called_once()
