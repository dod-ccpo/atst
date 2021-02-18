from flask import g, redirect, render_template
from flask import request as http_request
from flask import url_for

from atat.domain.application_roles import ApplicationRoles
from atat.domain.applications import Applications
from atat.domain.audit_log import AuditLog
from atat.domain.authz.decorator import user_can_access_decorator as user_can
from atat.domain.common import Paginator
from atat.domain.csp.cloud.exceptions import GeneralCSPException
from atat.domain.environment_roles import EnvironmentRoles
from atat.domain.environments import Environments
from atat.domain.exceptions import AlreadyExistsError
from atat.domain.invitations import ApplicationInvitations
from atat.domain.permission_sets import PermissionSets
from atat.domain.portfolios import Portfolios
from atat.forms.application import EditEnvironmentForm, NameAndDescriptionForm
from atat.forms.application_member import NewForm as NewMemberForm
from atat.forms.application_member import UpdateMemberForm
from atat.forms.data import ENV_ROLE_NO_ACCESS as NO_ACCESS
from atat.forms.member import NewForm as MemberForm
from atat.jobs import create_subscription as create_subscription_job
from atat.jobs import send_mail
from atat.models.permissions import Permissions
from atat.routes.errors import log_error
from atat.utils.flash import formatted_flash as flash
from atat.utils.localization import translate

from .blueprint import applications_bp

_APPLICATION_SETTINGS = "applications.settings"


def get_environments_obj_for_app(application):
    return sorted(
        [
            {
                "id": env.id,
                "name": env.name,
                "pending": env.is_pending,
                "edit_form": EditEnvironmentForm(obj=env),
                "member_count": len(env.roles),
                "members": sorted(
                    [
                        {
                            "user_name": env_role.application_role.user_name,
                            "status": env_role.status.value,
                        }
                        for env_role in env.roles
                    ],
                    key=lambda env_role: env_role["user_name"],
                ),
            }
            for env in application.environments
        ],
        key=lambda env: env["name"],
    )


def filter_perm_sets_data(member):
    perm_sets_data = {
        "perms_team_mgmt": bool(
            member.has_permission_set(PermissionSets.EDIT_APPLICATION_TEAM)
        ),
        "perms_env_mgmt": bool(
            member.has_permission_set(PermissionSets.EDIT_APPLICATION_ENVIRONMENTS)
        ),
    }

    return perm_sets_data


def filter_env_roles_data(roles):
    return sorted(
        [
            {
                "environment_id": str(role.environment.id),
                "environment_name": role.environment.name,
                "role": (role.role.value if role.role else "None"),
            }
            for role in roles
        ],
        key=lambda env: env["environment_name"],
    )


def filter_env_roles_form_data(member, environments):
    env_roles_form_data = []
    for env in environments:
        env_data = {
            "environment_id": str(env.id),
            "environment_name": env.name,
            "role": NO_ACCESS,
            "disabled": False,
        }
        env_roles_set = set(env.roles).intersection(set(member.environment_roles))

        if len(env_roles_set) == 1:
            (env_role,) = env_roles_set
            env_data["disabled"] = env_role.is_disabled
            if env_role.role:
                env_data["role"] = env_role.role.name

        env_roles_form_data.append(env_data)

    return env_roles_form_data


def get_members_data(application):
    members_data = []
    for member in application.members:
        permission_sets = filter_perm_sets_data(member)
        roles = EnvironmentRoles.get_for_application_member(member.id)
        environment_roles = filter_env_roles_data(roles)
        env_roles_form_data = filter_env_roles_form_data(
            member, application.environments
        )
        form = UpdateMemberForm(
            environment_roles=env_roles_form_data, **permission_sets
        )
        update_invite_form = (
            MemberForm(obj=member.latest_invitation)
            if member.latest_invitation and member.latest_invitation.can_resend
            else MemberForm()
        )

        members_data.append(
            {
                "role_id": member.id,
                "user_name": member.user_name,
                "permission_sets": permission_sets,
                "environment_roles": environment_roles,
                "role_status": member.display_status,
                "form": form,
                "update_invite_form": update_invite_form,
            }
        )

    return sorted(members_data, key=lambda member: member["user_name"])


def get_new_member_form(application):
    env_roles = sorted(
        [
            {"environment_id": e.id, "environment_name": e.name}
            for e in application.environments
        ],
        key=lambda role: role["environment_name"],
    )

    return NewMemberForm(data={"environment_roles": env_roles})


def render_settings_page(application, **kwargs):
    environments_obj = get_environments_obj_for_app(application=application)
    new_env_form = EditEnvironmentForm()
    pagination_opts = Paginator.get_pagination_opts(http_request)
    audit_events = AuditLog.get_application_events(application, pagination_opts)
    new_member_form = get_new_member_form(application)
    members = get_members_data(application)

    if "application_form" not in kwargs:
        kwargs["application_form"] = NameAndDescriptionForm(
            name=application.name, description=application.description
        )

    return render_template(
        "applications/settings.html",
        application=application,
        environments_obj=environments_obj,
        new_env_form=new_env_form,
        audit_events=audit_events,
        new_member_form=new_member_form,
        members=members,
        **kwargs,
    )


def send_application_invitation(invitee_email, inviter_name, token):
    body = render_template(
        "emails/application/invitation.txt", owner=inviter_name, token=token
    )
    send_mail.delay(
        [invitee_email],
        translate("email.application_invite", {"inviter_name": inviter_name}),
        body,
    )


def handle_create_member(application_id, form_data):
    application = Applications.get(application_id)
    form = NewMemberForm(form_data)

    if form.validate():
        cloud_id = ApplicationRoles.get_cloud_id_for_user(
            form.user_data.data["dod_id"], application.portfolio_id
        )
        try:
            invite = Applications.invite(
                application=application,
                inviter=g.current_user,
                user_data=form.user_data.data,
                permission_sets_names=form.data["permission_sets"],
                environment_roles_data=form.environment_roles.data,
                cloud_id=cloud_id,
            )

            send_application_invitation(
                invitee_email=invite.email,
                inviter_name=g.current_user.full_name,
                token=invite.token,
            )

            flash("new_application_member", user_name=invite.first_name)

        except AlreadyExistsError:
            return render_template(
                "error.html", message="There was an error processing your request."
            )


def handle_update_member(application_id, application_role_id, form_data):
    app_role = ApplicationRoles.get_by_id(application_role_id)
    application = Applications.get(application_id)
    existing_env_roles_data = filter_env_roles_form_data(
        app_role, application.environments
    )
    form = UpdateMemberForm(
        formdata=form_data, environment_roles=existing_env_roles_data
    )

    if form.validate():
        try:
            ApplicationRoles.update_permission_sets(
                app_role, form.data["permission_sets"]
            )

            for env_role in form.environment_roles:
                environment = Environments.get(env_role.environment_id.data)
                new_role = None if env_role.disabled.data else env_role.data["role"]
                Environments.update_env_role(environment, app_role, new_role)

            flash("application_member_updated", user_name=app_role.user_name)

        except GeneralCSPException as exc:
            log_error(exc)
            flash(
                "application_member_update_error", user_name=app_role.user_name,
            )


def handle_update_environment(form, application=None, environment=None):
    if form.validate():
        try:
            if environment:
                environment = Environments.update(
                    environment=environment, new_data={"name": form.name.data}
                )
                flash("application_environments_updated")
            else:
                environment = Environments.create(
                    g.current_user, application=application, name=form.name.data
                )
                flash("environment_added", environment_name=form.name.data)

            return environment

        except AlreadyExistsError:
            flash("application_environments_name_error", name=form.name.data)
            return False

    else:
        return False


def handle_update_application(form, application_id=None, portfolio_id=None):
    if form.validate():
        application = None

        try:
            if application_id:
                application = Applications.get(application_id)
                application = Applications.update(application, form.data)
                flash("application_updated", application_name=application.name)
            else:
                portfolio = Portfolios.get_for_update(portfolio_id)
                application = Applications.create(
                    g.current_user, portfolio, **form.data
                )
                flash("application_created", application_name=application.name)

            return application

        except AlreadyExistsError:
            flash("application_name_error", name=form.data["name"])
            return False


@applications_bp.route("/applications/<application_id>/settings")
@user_can(Permissions.VIEW_APPLICATION, message="view application edit form")
def settings(application_id):
    application = Applications.get(application_id)

    return render_settings_page(application=application,)


@applications_bp.route("/environments/<environment_id>/edit", methods=["POST"])
@user_can(Permissions.EDIT_ENVIRONMENT, message="edit application environments")
def update_environment(environment_id):
    environment = Environments.get(environment_id)
    application = environment.application

    env_form = EditEnvironmentForm(obj=environment, formdata=http_request.form)
    updated_environment = handle_update_environment(
        form=env_form, application=application, environment=environment
    )

    if updated_environment:
        return redirect(
            url_for(
                _APPLICATION_SETTINGS,
                application_id=application.id,
                fragment="application-environments",
                _anchor="application-environments",
            )
        )
    else:
        return (render_settings_page(application=application, show_flash=True), 400)


@applications_bp.route(
    "/applications/<application_id>/environments/new", methods=["POST"]
)
@user_can(Permissions.CREATE_ENVIRONMENT, message="create application environment")
def new_environment(application_id):
    application = Applications.get(application_id)
    env_form = EditEnvironmentForm(formdata=http_request.form)
    environment = handle_update_environment(form=env_form, application=application)

    if environment:
        return redirect(
            url_for(
                _APPLICATION_SETTINGS,
                application_id=application.id,
                fragment="application-environments",
                _anchor="application-environments",
            )
        )
    else:
        return (render_settings_page(application=application, show_flash=True), 400)


@applications_bp.route("/applications/<application_id>/edit", methods=["POST"])
@user_can(Permissions.EDIT_APPLICATION, message="update application")
def update(application_id):
    application = Applications.get(application_id)
    form = NameAndDescriptionForm(http_request.form)
    updated_application = handle_update_application(form, application_id)

    if updated_application:
        return redirect(
            url_for(
                "applications.portfolio_applications",
                portfolio_id=application.portfolio_id,
            )
        )
    else:
        return (
            render_settings_page(application=application, show_flash=True),
            400,
        )


@applications_bp.route("/environments/<environment_id>/delete", methods=["POST"])
@user_can(Permissions.DELETE_ENVIRONMENT, message="delete environment")
def delete_environment(environment_id):
    environment = Environments.get(environment_id)
    Environments.delete(environment=environment, commit=True)

    flash("environment_deleted", environment_name=environment.name)

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=environment.application_id,
            _anchor="application-environments",
            fragment="application-environments",
        )
    )


@applications_bp.route("/application/<application_id>/members/new", methods=["POST"])
@user_can(
    Permissions.CREATE_APPLICATION_MEMBER, message="create new application member"
)
def create_member(application_id):
    handle_create_member(application_id, http_request.form)
    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=application_id,
            fragment="application-members",
            _anchor="application-members",
        )
    )


@applications_bp.route(
    "/applications/<application_id>/members/<application_role_id>/delete",
    methods=["POST"],
)
@user_can(Permissions.DELETE_APPLICATION_MEMBER, message="remove application member")
def remove_member(application_id, application_role_id):
    application_role = ApplicationRoles.get_by_id(application_role_id)
    ApplicationRoles.disable(application_role)

    flash(
        "application_member_removed",
        user_name=application_role.user_name,
        application_name=g.application.name,
    )

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            _anchor="application-members",
            application_id=g.application.id,
            fragment="application-members",
        )
    )


@applications_bp.route(
    "/applications/<application_id>/members/<application_role_id>/update",
    methods=["POST"],
)
@user_can(Permissions.EDIT_APPLICATION_MEMBER, message="update application member")
def update_member(application_id, application_role_id):

    handle_update_member(application_id, application_role_id, http_request.form)

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=application_id,
            fragment="application-members",
            _anchor="application-members",
        )
    )


@applications_bp.route(
    "/applications/<application_id>/members/<application_role_id>/revoke_invite",
    methods=["POST"],
)
@user_can(
    Permissions.DELETE_APPLICATION_MEMBER, message="revoke application invitation"
)
def revoke_invite(application_id, application_role_id):
    app_role = ApplicationRoles.get_by_id(application_role_id)
    invite = app_role.latest_invitation

    if invite.is_pending:
        ApplicationInvitations.revoke(invite.token)
        flash(
            "invite_revoked",
            resource="Application",
            user_name=app_role.user_name,
            resource_name=g.application.name,
        )
    else:
        flash(
            "application_invite_error",
            user_name=app_role.user_name,
            application_name=g.application.name,
        )

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=application_id,
            fragment="application-members",
            _anchor="application-members",
        )
    )


@applications_bp.route(
    "/applications/<application_id>/members/<application_role_id>/resend_invite",
    methods=["POST"],
)
@user_can(Permissions.EDIT_APPLICATION_MEMBER, message="resend application invitation")
def resend_invite(application_id, application_role_id):
    app_role = ApplicationRoles.get_by_id(application_role_id)
    invite = app_role.latest_invitation
    form = MemberForm(http_request.form)

    if form.validate():
        new_invite = ApplicationInvitations.resend(
            g.current_user, invite.token, form.data
        )

        send_application_invitation(
            invitee_email=new_invite.email,
            inviter_name=g.current_user.full_name,
            token=new_invite.token,
        )

        flash("application_invite_resent", email=new_invite.email)
    else:
        flash(
            "application_invite_error",
            user_name=app_role.user_name,
            application_name=g.application.name,
        )

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=application_id,
            fragment="application-members",
            _anchor="application-members",
        )
    )


@applications_bp.route(
    "/environments/<environment_id>/add_subscription", methods=["POST"]
)
@user_can(Permissions.EDIT_ENVIRONMENT, message="create new environment subscription")
def create_subscription(environment_id):
    environment = Environments.get(environment_id)
    create_subscription_job.delay(environment_id=environment.id)

    return redirect(
        url_for(
            _APPLICATION_SETTINGS,
            application_id=environment.application.id,
            fragment="application-environments",
            _anchor="application-environments",
        )
    )
