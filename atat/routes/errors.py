import werkzeug.exceptions as werkzeug_exceptions
from flask import current_app, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

import atat.domain.exceptions as exceptions
from atat.domain.invitations import ExpiredError as InvitationExpiredError
from atat.domain.invitations import InvitationError
from atat.domain.invitations import WrongUserError as InvitationWrongUserError
from atat.domain.portfolios import PortfolioError
from atat.utils.flash import formatted_flash as flash
from atat.utils.localization import translate

NO_NOTIFY_STATUS_CODES = set([404, 401])


def log_error(e):
    error_message = e.message if hasattr(e, "message") else str(e)
    current_app.logger.exception(error_message)


def notify(e, message, code):
    if code not in NO_NOTIFY_STATUS_CODES:
        current_app.notification_sender.send(message)


def handle_error(e, message=translate("errors.not_found"), code=404):
    log_error(e)
    notify(e, message, code)
    return (render_template("error.html", message=message, code=code), code)


def make_error_pages(app):
    @app.errorhandler(werkzeug_exceptions.NotFound)
    @app.errorhandler(exceptions.NotFoundError)
    @app.errorhandler(exceptions.UnauthorizedError)
    @app.errorhandler(PortfolioError)
    @app.errorhandler(exceptions.NoAccessError)
    # pylint: disable=unused-variable
    def not_found(e):
        return handle_error(e)

    @app.errorhandler(exceptions.UnauthenticatedError)
    # pylint: disable=unused-variable
    def unauthorized(e):
        return handle_error(e, message="Login Failed", code=401)

    @app.errorhandler(CSRFError)
    # pylint: disable=unused-variable
    def session_expired(e):
        log_error(e)
        url_args = {"next": request.path}
        flash("session_expired")
        if request.method == "POST":
            url_args[app.form_cache.PARAM_NAME] = app.form_cache.write(request.form)
        return redirect(url_for("atat.root", **url_args))

    @app.errorhandler(Exception)
    # pylint: disable=unused-variable
    def exception(e):
        if current_app.debug:
            raise e
        return handle_error(e, message="An Unexpected Error Occurred", code=500)

    @app.errorhandler(InvitationError)
    @app.errorhandler(InvitationWrongUserError)
    # pylint: disable=unused-variable
    def invalid_invitation(e):
        return handle_error(e, message="The link you followed is invalid.", code=404)

    @app.errorhandler(InvitationExpiredError)
    # pylint: disable=unused-variable
    def invalid_invitation(e):
        return handle_error(
            e, message="The invitation you followed has expired.", code=404
        )

    return app
