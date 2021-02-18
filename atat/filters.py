import re
from decimal import DivisionByZero as DivisionByZeroException
from decimal import InvalidOperation
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from flask import render_template
from jinja2 import contextfilter
from jinja2.exceptions import TemplateNotFound

from atat.utils.localization import translate


def icon_svg(name):
    with open("static/icons/" + name + ".svg") as contents:
        return contents.read()


def dollars(value):
    try:
        number_value = float(value)
    except ValueError:
        number_value = 0
    return "${:,.2f}".format(number_value)


def with_extra_params(url, **params):
    """
    Takes an existing url and safely appends additional query parms.
    """
    parsed_url = urlparse(url)
    parsed_params = parse_qs(parsed_url.query)
    new_params = {**parsed_params, **params}
    parsed_url = parsed_url._replace(query=urlencode(new_params))
    return urlunparse(parsed_url)


def us_phone(number):
    if not number:
        return ""
    phone = re.sub(r"\D", "", number)
    return "+1 ({}) {} - {}".format(phone[0:3], phone[3:6], phone[6:])


def obligated_funding_graph_width(values):
    numerator, denominator = values
    try:
        return (numerator / denominator) * 100
    except (DivisionByZeroException, InvalidOperation):
        return 0


def formatted_date(value, formatter="%m/%d/%Y"):
    if value:
        return value.strftime(formatter)
    else:
        return "-"


def page_window(pagination, size=2):
    page = pagination.page
    num_pages = pagination.pages

    over = max(0, page + size - num_pages)
    under = min(0, page - size - 1)

    return (max(1, (page - size) - over), min(num_pages, (page + size) - under))


def render_audit_event(event):
    template_name = "audit_log/events/{}.html".format(event.resource_type)
    try:
        return render_template(template_name, event=event)
    except TemplateNotFound:
        return render_template("audit_log/events/default.html", event=event)


def register_filters(app):
    app.jinja_env.filters["iconSvg"] = icon_svg
    app.jinja_env.filters["dollars"] = dollars
    app.jinja_env.filters["usPhone"] = us_phone
    app.jinja_env.filters["formattedDate"] = formatted_date
    app.jinja_env.filters["pageWindow"] = page_window
    app.jinja_env.filters["renderAuditEvent"] = render_audit_event
    app.jinja_env.filters["withExtraParams"] = with_extra_params
    app.jinja_env.filters["obligatedFundingGraphWidth"] = obligated_funding_graph_width

    @contextfilter
    def translate_without_cache(context, *kwargs):
        return translate(*kwargs)

    if app.config["DEBUG"]:
        app.jinja_env.filters["translate"] = translate_without_cache
    else:
        app.jinja_env.filters["translate"] = translate
