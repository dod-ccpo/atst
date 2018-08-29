from flask import render_template, redirect, url_for
from flask import request as http_request

from . import requests_bp
from atst.domain.requests import Requests
from atst.forms.financial import FinancialForm, ExtendedFinancialForm


def financial_form(data):
    if http_request.args.get("extended"):
        return ExtendedFinancialForm(data=data)
    else:
        return FinancialForm(data=data)


@requests_bp.route("/requests/verify/<string:request_id>", methods=["GET"])
def financial_verification(request_id=None):
    request = Requests.get(request_id)
    form = financial_form(request.body.get("financial_verification"))
    return render_template(
        "requests/financial_verification.html",
        f=form,
        request_id=request_id,
        extended=http_request.args.get("extended"),
    )


@requests_bp.route("/requests/verify/<string:request_id>", methods=["POST"])
def update_financial_verification(request_id):
    post_data = http_request.form
    existing_request = Requests.get(request_id)
    form = financial_form(post_data)
    rerender_args = dict(
        request_id=request_id, f=form, extended=http_request.args.get("extended")
    )

    if form.validate():
        valid = form.perform_extra_validation(
            existing_request.body.get("financial_verification")
        )
        updated_request = Requests.update_financial_verification(request_id, form.data)
        if valid:
            submitted_request = Requests.submit_financial_verification(updated_request)
            if updated_request.is_financially_verified:
                new_workspace = Requests.approve_and_create_workspace(submitted_request)
                return redirect(
                    url_for(
                        "workspaces.new_project",
                        workspace_id=new_workspace.id,
                        newWorkspace=True,
                    )
                )

        else:
            form.reset()
            return render_template(
                "requests/financial_verification.html", **rerender_args
            )

    else:
        form.reset()
        return render_template("requests/financial_verification.html", **rerender_args)
