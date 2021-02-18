import datetime
import json
import logging

from flask import g, has_request_context, request, session


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():
            if getattr(g, "current_user", None):
                record.dod_edipi = g.current_user.dod_id

            user_id = session.get("user_id")
            if user_id:
                record.user_id = str(user_id)
                record.logged_in = True
            else:
                record.logged_in = False

            if request.environ.get("HTTP_X_REQUEST_ID"):
                record.request_id = request.environ.get("HTTP_X_REQUEST_ID")

        return True


def epoch_to_iso8601(ts):
    dt = datetime.datetime.utcfromtimestamp(ts)
    return dt.replace(tzinfo=datetime.timezone.utc).isoformat()


class JsonFormatter(logging.Formatter):
    _DEFAULT_RECORD_FIELDS = [
        ("timestamp", lambda r: epoch_to_iso8601(r.created)),
        ("version", lambda r: 1),
        ("request_id", lambda r: r.__dict__.get("request_id")),
        ("user_id", lambda r: r.__dict__.get("user_id")),
        ("dod_edipi", lambda r: r.__dict__.get("dod_edipi")),
        ("logged_in", lambda r: r.__dict__.get("logged_in")),
        ("severity", lambda r: r.levelname),
        ("tags", lambda r: r.__dict__.get("tags")),
        ("audit_event", lambda r: r.__dict__.get("audit_event")),
    ]

    def __init__(self, *args, source="atat", **kwargs):
        self.source = source
        super().__init__()

    def format(self, record, *args, **kwargs):
        message_dict = {"source": self.source}

        for field, func in self._DEFAULT_RECORD_FIELDS:
            result = func(record)
            if result is not None:
                message_dict[field] = result

        if record.args:
            message_dict["message"] = record.msg % record.args
        else:
            message_dict["message"] = record.msg

        if record.__dict__.get("exc_info") is not None:
            message_dict["details"] = {
                "backtrace": self.formatException(record.exc_info),
                "exception": str(record.exc_info[1]),
            }

        return json.dumps(message_dict)
