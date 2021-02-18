import pendulum
from flask import g, redirect, render_template
from flask import request as http_request
from flask import url_for

from atat.domain.authz.decorator import user_can_access_decorator as user_can
from atat.domain.portfolios import Portfolios
from atat.domain.reports import Reports
from atat.forms.portfolio import PortfolioCreationForm
from atat.models.permissions import Permissions
from atat.utils.flash import formatted_flash as flash

from .blueprint import portfolios_bp


@portfolios_bp.route("/portfolios/new")
def new_portfolio_step_1():
    form = PortfolioCreationForm()
    return render_template("portfolios/new/step_1.html", form=form)


@portfolios_bp.route("/portfolios", methods=["POST"])
def create_portfolio():
    form = PortfolioCreationForm(http_request.form)

    if form.validate():
        portfolio = Portfolios.create(user=g.current_user, portfolio_attrs=form.data)
        return redirect(
            url_for("task_orders.portfolio_funding", portfolio_id=portfolio.id)
        )
    else:
        return render_template("portfolios/new/step_1.html", form=form), 400


@portfolios_bp.route("/portfolios/<portfolio_id>/reports")
@user_can(Permissions.VIEW_PORTFOLIO_REPORTS, message="view portfolio reports")
def reports(portfolio_id):
    portfolio = Portfolios.get(g.current_user, portfolio_id)
    spending = Reports.get_portfolio_spending(portfolio)
    obligated = portfolio.total_obligated_funds
    remaining = obligated - (spending["invoiced"] + spending["estimated"])

    current_obligated_funds = {
        **spending,
        "obligated": obligated,
        "remaining": remaining,
    }

    if current_obligated_funds["remaining"] < 0:
        flash("insufficient_funds")

    return render_template(
        "portfolios/reports/index.html",
        portfolio=portfolio,
        # wrapped in str() because this sum returns a Decimal object
        total_portfolio_value=str(portfolio.total_obligated_funds),
        current_obligated_funds=current_obligated_funds,
        expired_task_orders=Reports.expired_task_orders(portfolio),
        retrieved=pendulum.now(tz="UTC"),  # mocked datetime of reporting data retrival
    )
