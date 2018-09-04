from flask import Blueprint, render_template, g, redirect, session, url_for, request
from flask import current_app as app
import pendulum

from atst.domain.requests import Requests
from atst.domain.users import Users
from atst.domain.authnid import AuthenticationContext


bp = Blueprint("atst", __name__)


@bp.route("/")
def root():
    return render_template("root.html")


@bp.route("/home")
def home():
    return render_template("home.html")


@bp.route("/styleguide")
def styleguide():
    return render_template("styleguide.html")


@bp.route("/<path:path>")
def catch_all(path):
    return render_template("{}.html".format(path))


def _make_authentication_context():
    return AuthenticationContext(
        crl_cache=app.crl_cache,
        auth_status=request.environ.get("HTTP_X_SSL_CLIENT_VERIFY"),
        sdn=request.environ.get("HTTP_X_SSL_CLIENT_S_DN"),
        cert=request.environ.get("HTTP_X_SSL_CLIENT_CERT"),
    )


@bp.route("/login-redirect")
def login_redirect():
    auth_context = _make_authentication_context()
    auth_context.authenticate()
    user = auth_context.get_user()
    session["user_id"] = user.id

    if user.atat_role.name == "ccpo":
        return redirect(url_for("requests.requests_index"))
    else:
        return redirect(url_for("requests.requests_index"))


def _is_valid_certificate(request):
    cert = request.environ.get("HTTP_X_SSL_CLIENT_CERT")
    if cert:
        result = app.crl_validator.validate(cert.encode())
        return result
    else:
        return False
