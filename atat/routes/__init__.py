import os
import urllib.parse as url

from flask import Blueprint
from flask import current_app as app
from flask import g, make_response, redirect, render_template, request, session, url_for
from jinja2.exceptions import TemplateNotFound

from atat.domain.auth import logout as _logout
from atat.domain.users import Users
from atat.routes.routes_helpers import match_url_pattern
from atat.routes.saml_helpers import (
    get_user_from_saml_attributes,
    init_saml_auth_dev,
    load_attributes_from_assertion,
    prepare_idp_url,
)
from atat.utils.flash import formatted_flash as flash

bp = Blueprint("atat", __name__)


@bp.route("/")
def root():
    if g.current_user:
        return redirect(url_for(".home"))

    redirect_url = url_for(".login")
    if request.args.get("next"):
        redirect_url = url.urljoin(
            redirect_url,
            "?{}".format(url.urlencode({"next": request.args.get("next")})),
        )
        flash("login_next")

    return render_template("login.html", redirect_url=redirect_url)


@bp.route("/home")
def home():
    return render_template("home.html")


def redirect_after_login_url(next_param=None):
    returl = next_param or request.args.get("next")
    if match_url_pattern(returl):
        param_name = request.args.get(app.form_cache.PARAM_NAME)
        if param_name:
            returl += "?" + url.urlencode({app.form_cache.PARAM_NAME: param_name})
        return returl
    else:
        return url_for("atat.home")


def current_user_setup(user):
    session["user_id"] = user.id
    session["last_login"] = user.last_login
    app.session_limiter.on_login(user)
    app.logger.info("authentication succeeded for user with EDIPI %s", user.dod_id)
    Users.update_last_login(user)


@bp.route("/logout")
def logout():
    login_method = session.pop("login_method", "main")
    _logout()
    logout_url = url_for(".root")

    if login_method == "dev":
        saml_auth = init_saml_auth_dev(request)
        logout_url = saml_auth.logout(return_to=logout_url)

    response = make_response(redirect(logout_url))
    response.set_cookie(
        "expandSidenav", "", expires=0, httponly=True, samesite="Lax", secure=True
    )
    flash("logged_out")
    return response


@bp.route("/login", methods=["GET"])
def login():
    saml_login_uri = prepare_idp_url(request)
    return redirect(saml_login_uri)


@bp.route("/login", methods=["POST"])
def handle_login_response():
    if "acs" in request.args:
        attributes = load_attributes_from_assertion(request)
        user = get_user_from_saml_attributes(attributes)

        next_param = session.pop("query_string_parameters", {}).get("next_param", None)
        current_user_setup(user)
        return redirect(redirect_after_login_url(next_param))
