from functools import wraps

from flask import current_app as app
from flask import g, request

from atat.domain.exceptions import UnauthorizedError

from . import user_can_access


def check_access(permission, message, override, *args, **kwargs):
    access_args = {
        "message": message,
        "portfolio": g.portfolio,
        "application": g.application,
    }

    if override is not None and override(g.current_user, **access_args, **kwargs):
        return True

    return user_can_access(g.current_user, permission, **access_args)


def user_can_access_decorator(permission, message=None, override=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                check_access(permission, message, override, *args, **kwargs)
                app.logger.info(
                    "User %s accessed %s %s",
                    g.current_user.id,
                    request.method,
                    request.path,
                    extra={"tags": ["access", "success"]},
                )

                return f(*args, **kwargs)
            except UnauthorizedError as err:
                app.logger.warning(
                    "User %s denied access %s %s",
                    g.current_user.id,
                    request.method,
                    request.path,
                    extra={"tags": ["access", "failure"]},
                )

                raise err

        return decorated_function

    return decorator
