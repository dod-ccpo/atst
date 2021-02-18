from flask import _request_ctx_stack as request_ctx_stack
from flask import current_app as app
from flask import g, redirect, request, session, url_for
from werkzeug.datastructures import ImmutableTypeConversionDict

from atat.domain.users import Users

# Routes not included in this list are not accessible without an authenticated browser session
UNPROTECTED_ROUTES = [
    "atat.root",
    "dev.login_dev",
    "local_access.dev_new_user",
    "local_access.local_access",
    "atat.login_redirect",
    "atat.logout",
    "atat.unauthorized",
    "static",
    "atat.login",
    "atat.handle_login_response",
]


def apply_authentication(app):
    @app.before_request
    # pylint: disable=unused-variable
    def enforce_login():
        user = get_current_user()
        if user:
            g.current_user = user
            g.last_login = get_last_login()

            if should_redirect_to_user_profile(request, user):
                return redirect(url_for("users.user", next=request.path))
        elif not _unprotected_route(request):
            return redirect(url_for("atat.root", next=request.path))


def should_redirect_to_user_profile(request, user):
    has_complete_profile = user.profile_complete
    is_unprotected_route = _unprotected_route(request)
    is_requesting_user_endpoint = request.endpoint in [
        "users.user",
        "users.update_user",
    ]

    if has_complete_profile or is_unprotected_route or is_requesting_user_endpoint:
        return False

    return True


def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return Users.get(user_id)
    else:
        return False


def get_last_login():
    return session.get("user_id") and session.get("last_login")


def _nullify_session(session):
    session_key = f"{app.config.get('SESSION_KEY_PREFIX')}{session.sid}"
    app.redis.delete(session_key)
    request.cookies = ImmutableTypeConversionDict()
    request_ctx_stack.top.session = app.session_interface.open_session(app, request)


def _current_dod_id():
    return g.current_user.dod_id if session.get("user_id") else None


def logout():
    dod_id = _current_dod_id()

    _nullify_session(session)

    if dod_id:
        app.logger.info("user with EDIPI %s has logged out", dod_id)
    else:
        app.logger.info("unauthenticated user has logged out")


def _unprotected_route(request):
    if request.endpoint in UNPROTECTED_ROUTES:
        return True
