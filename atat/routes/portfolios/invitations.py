from flask import g, redirect, render_template
from flask import request as http_request
from flask import url_for

import atat.forms.portfolio_member as member_forms
from atat.domain.authz.decorator import user_can_access_decorator as user_can
from atat.domain.exceptions import AlreadyExistsError
from atat.domain.invitations import PortfolioInvitations
from atat.domain.portfolios import Portfolios
from atat.jobs import send_mail
from atat.models import Permissions
from atat.utils.flash import formatted_flash as flash
from atat.utils.localization import translate

from .blueprint import portfolios_bp

_PORTFOLIO_ADMIN_URL = "portfolios.admin"


def send_portfolio_invitation(invitee_email, inviter_name, token):
    body = render_template(
        "emails/portfolio/invitation.txt", owner=inviter_name, token=token
    )
    send_mail.delay(
        [invitee_email],
        translate("email.portfolio_invite", {"inviter_name": inviter_name}),
        body,
    )


@portfolios_bp.route("/portfolios/invitations/<portfolio_token>", methods=["GET"])
def accept_invitation(portfolio_token):
    invite = PortfolioInvitations.accept(g.current_user, portfolio_token)

    return redirect(
        url_for("applications.portfolio_applications", portfolio_id=invite.portfolio.id)
    )


@portfolios_bp.route(
    "/portfolios/<portfolio_id>/invitations/<portfolio_token>/revoke", methods=["POST"]
)
@user_can(Permissions.EDIT_PORTFOLIO_USERS, message="revoke invitation")
def revoke_invitation(portfolio_id, portfolio_token):
    invite = PortfolioInvitations.revoke(portfolio_token)

    flash(
        "invite_revoked",
        resource="Portfolio",
        user_name=invite.user_name,
        resource_name=g.portfolio.name,
    )
    return redirect(
        url_for(
            _PORTFOLIO_ADMIN_URL,
            portfolio_id=portfolio_id,
            _anchor="portfolio-members",
            fragment="portfolio-members",
        )
    )


@portfolios_bp.route(
    "/portfolios/<portfolio_id>/invitations/<portfolio_token>/resend", methods=["POST"]
)
@user_can(Permissions.EDIT_PORTFOLIO_USERS, message="resend invitation")
def resend_invitation(portfolio_id, portfolio_token):
    form = member_forms.NewForm(http_request.form)

    if form.validate():
        invite = PortfolioInvitations.resend(
            g.current_user, portfolio_token, form.data["user_data"]
        )
        send_portfolio_invitation(
            invitee_email=invite.email,
            inviter_name=g.current_user.full_name,
            token=invite.token,
        )
        flash("resend_portfolio_invitation", email=invite.email)
    else:
        user_name = f"{form['user_data']['first_name'].data} {form['user_data']['last_name'].data}"
        flash("resend_portfolio_invitation_error", user_name=user_name)

    return redirect(
        url_for(
            _PORTFOLIO_ADMIN_URL,
            portfolio_id=portfolio_id,
            fragment="portfolio-members",
            _anchor="portfolio-members",
        )
    )


@portfolios_bp.route("/portfolios/<portfolio_id>/members/new", methods=["POST"])
@user_can(Permissions.CREATE_PORTFOLIO_USERS, message="create new portfolio member")
def invite_member(portfolio_id):
    portfolio = Portfolios.get(g.current_user, portfolio_id)
    form = member_forms.NewForm(http_request.form)

    if form.validate():
        try:
            invite = Portfolios.invite(portfolio, g.current_user, form.data)
            send_portfolio_invitation(
                invitee_email=invite.email,
                inviter_name=g.current_user.full_name,
                token=invite.token,
            )

            flash(
                "new_portfolio_member", user_name=invite.user_name, portfolio=portfolio
            )

        except AlreadyExistsError:
            return render_template(
                "error.html", message="There was an error processing your request."
            )

    # TODO: flash error message if form is invalid

    return redirect(
        url_for(
            _PORTFOLIO_ADMIN_URL,
            portfolio_id=portfolio_id,
            fragment="portfolio-members",
            _anchor="portfolio-members",
        )
    )
