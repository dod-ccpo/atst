from secrets import token_urlsafe
from smtplib import SMTPException

import pendulum
from azure.core.exceptions import AzureError
from celery import Task
from flask import current_app as app

from atat.database import db
from atat.domain.application_roles import ApplicationRoles
from atat.domain.applications import Applications
from atat.domain.csp.cloud import CloudProviderInterface
from atat.domain.csp.cloud.exceptions import GeneralCSPException
from atat.domain.csp.cloud.models import (
    ApplicationCSPPayload,
    BillingInstructionCSPPayload,
    EnvironmentCSPPayload,
    SubscriptionCreationCSPPayload,
    UserCSPPayload,
    UserRoleCSPPayload,
)
from atat.domain.csp.cloud.utils import generate_user_principal_name
from atat.domain.environment_roles import EnvironmentRoles
from atat.domain.environments import Environments
from atat.domain.portfolios import Portfolios
from atat.domain.task_orders import TaskOrders
from atat.models import CSPRole, JobFailure
from atat.models.mixins.state_machines import PortfolioStates
from atat.models.utils import claim_for_update, claim_many_for_update
from atat.queue import celery
from atat.utils.localization import translate


class RecordFailure(celery.Task):
    _ENTITIES = [
        "portfolio_id",
        "application_id",
        "environment_id",
        "environment_role_id",
    ]

    def _derive_entity_info(self, kwargs):
        matches = [e for e in self._ENTITIES if e in kwargs.keys()]
        if matches:
            match = matches[0]
            return {"entity": match.replace("_id", ""), "entity_id": kwargs[match]}
        else:
            return None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        info = self._derive_entity_info(kwargs)
        if info:
            failure = JobFailure(**info, task_id=task_id)
            db.session.add(failure)
            db.session.commit()


@celery.task(ignore_result=True)
def send_mail(recipients, subject, body, attachments=[]):
    app.mailer.send(recipients, subject, body, attachments)


@celery.task(ignore_result=True)
def send_notification_mail(recipients, subject, body):
    app.logger.info(
        "Sending a notification to these recipients: %s\n\nSubject: %s\n\n%s",
        recipients,
        subject,
        body,
    )
    app.mailer.send(recipients, subject, body)


def do_create_application(csp: CloudProviderInterface, application_id=None):
    application = Applications.get(application_id)

    with claim_for_update(application) as application:

        if application.cloud_id:
            app.logger.warning(
                "Attempted to create application %s when it already exists.",
                application.cloud_id,
            )
            return

        csp_details = application.portfolio.csp_data
        tenant_id = csp_details["tenant_id"]
        parent_id = f"/providers/Microsoft.Management/managementGroups/{tenant_id}"

        app.logger.debug("application.id = %s", application.id)
        app.logger.debug("application.portfolio.id = %s", application.portfolio.id)
        app.logger.debug("tenant_id = %s", tenant_id)
        app.logger.debug("parent_id = %s", parent_id)

        payload = ApplicationCSPPayload(
            tenant_id=tenant_id, display_name=application.name, parent_id=parent_id
        )

        app_result = csp.create_application(payload)
        application.cloud_id = (
            f"/providers/Microsoft.Management/managementGroups/{app_result.name}"
        )
        db.session.add(application)
        db.session.commit()


def do_create_user(csp: CloudProviderInterface, application_role_ids=None):
    if not application_role_ids:
        return

    app_roles = ApplicationRoles.get_many(application_role_ids)

    with claim_many_for_update(app_roles) as app_roles:

        for ar in app_roles:
            if ar.cloud_id:
                app.logger.warning(
                    "Application role cloud ID %s already present.", ar.cloud_id
                )
                return

        csp_details = app_roles[0].application.portfolio.csp_data
        user = app_roles[0].user
        cloud_id = ApplicationRoles.get_cloud_id_for_user(
            user.dod_id, app_roles[0].portfolio_id
        )

        payload = UserCSPPayload(
            tenant_id=csp_details.get("tenant_id"),
            tenant_host_name=csp_details.get("domain_name"),
            display_name=user.full_name,
            email=user.email,
        )

        if cloud_id is None:
            result = csp.create_user(payload)
            cloud_id = result.id

        for app_role in app_roles:
            app_role.cloud_id = cloud_id
            db.session.add(app_role)

        db.session.commit()
        username = payload.user_principal_name
        send_mail(
            recipients=[user.email],
            subject=translate("email.app_role_created.subject"),
            body=translate(
                "email.app_role_created.body",
                {"url": app.config.get("AZURE_LOGIN_URL"), "username": username},
            ),
        )
        app.logger.info(
            "Application role created notification email sent. User id: %s", user.id
        )


def log_do_create_environment(portfolio_id, parent_id, tenant_id):
    app.logger.debug("environment.portfolio.id = %s", portfolio_id)
    app.logger.debug("parent_id = %s", parent_id)
    app.logger.debug("tenant_id = %s", tenant_id)


def do_create_environment(csp: CloudProviderInterface, environment_id=None):
    """Creates an environment and spawns a task to create a subscription 
    for that environment in the CSP.
    """

    environment = Environments.get(environment_id)

    with claim_for_update(environment) as environment:

        if environment.cloud_id is not None:
            app.logger.warning(
                "Environment cloud ID %s already present.", environment.cloud_id
            )
            return

        parent_id = environment.application.cloud_id
        tenant_id = environment.portfolio.csp_data["tenant_id"]

        log_do_create_environment(environment.portfolio.id, parent_id, tenant_id)

        payload = EnvironmentCSPPayload(
            tenant_id=tenant_id, display_name=environment.name, parent_id=parent_id
        )
        env_result = csp.create_environment(payload)
        Environments.update(environment, new_data={"cloud_id": env_result.id})

        app.logger.info("Created environment %s", env_result.name)
        async_result = create_subscription.delay(environment_id=environment.id)
        app.logger.info(
            "Attempting to create subscription for environment %s [Task ID: %s])",
            env_result.name,
            async_result.task_id,
        )


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def create_subscription(self, environment_id=None):
    do_create_subscription(app.csp.cloud, environment_id=environment_id)
    return environment_id


def build_subscription_payload(environment) -> SubscriptionCreationCSPPayload:
    csp_data = environment.portfolio.csp_data
    parent_group_id = environment.cloud_id
    invoice_section_name = csp_data["billing_profile_properties"]["invoice_sections"][
        0
    ]["invoice_section_name"]

    display_name = (
        f"{environment.application.name}-{environment.name}-{token_urlsafe(6)}"
    )

    return SubscriptionCreationCSPPayload(
        tenant_id=csp_data.get("tenant_id"),
        display_name=display_name,
        parent_group_id=parent_group_id,
        billing_account_name=app.config["AZURE_BILLING_ACCOUNT_NAME"],
        billing_profile_name=csp_data.get("billing_profile_name"),
        invoice_section_name=invoice_section_name,
    )


def do_create_subscription(csp: CloudProviderInterface, environment_id=None):
    """Creates a subscription under a management group for an environment
    
    Creating a subscription is a long-running async job in Azure. For our 
    purposes, we don't track the success or failure of that job. We only ensure 
    that a request to kick off this async job is accepted.
    """
    environment = Environments.get(environment_id)
    payload = build_subscription_payload(environment)
    try:
        csp.create_subscription(payload)
    except GeneralCSPException as e:
        app.logger.warning(
            "Unable to create subscription for environment %s.", environment.id,
        )
        raise e


def do_create_environment_role(csp: CloudProviderInterface, environment_role_id=None):
    env_role = EnvironmentRoles.get_by_id(environment_role_id)

    with claim_for_update(env_role) as env_role:

        if env_role.cloud_id is not None:
            app.logger.warning(
                "Attempting to create an environment role %s that already exists.",
                env_role.cloud_id,
            )
            return

        env = env_role.environment
        csp_details = env.portfolio.csp_data
        app_role = env_role.application_role

        role = None
        if env_role.role == CSPRole.ADMIN:
            role = UserRoleCSPPayload.Roles.owner
        elif env_role.role == CSPRole.BILLING_READ:
            role = UserRoleCSPPayload.Roles.billing
        elif env_role.role == CSPRole.CONTRIBUTOR:
            role = UserRoleCSPPayload.Roles.contributor

        payload = UserRoleCSPPayload(
            tenant_id=csp_details.get("tenant_id"),
            management_group_id=env.cloud_id,
            user_object_id=app_role.cloud_id,
            role=role,
        )
        result = csp.create_user_role(payload)
        EnvironmentRoles.activate(env_role, result.id)

        app.logger.info("Created environment role %s", env_role.cloud_id)

        user = env_role.application_role.user
        domain_name = csp_details.get("domain_name")
        username = generate_user_principal_name(user.full_name, domain_name,)
        send_mail(
            recipients=[user.email],
            subject=translate("email.azure_account_update.subject"),
            body=translate(
                "email.azure_account_update.body",
                {"url": app.config.get("AZURE_LOGIN_URL"), "username": username},
            ),
        )
        app.logger.info(
            "Notification email sent for environment role creation. User id: %s",
            user.id,
        )


def render_email(template_path, context):
    return app.jinja_env.get_template(template_path).render(context)


def send_ppoc_email(portfolio_dict):
    ppoc_email = portfolio_dict.get("password_recovery_email_address")
    user_id = portfolio_dict.get("user_id")
    domain_name = portfolio_dict.get("domain_name")
    username = generate_user_principal_name(user_id, domain_name)
    send_mail(
        recipients=[ppoc_email],
        subject=translate("email.portfolio_ready.subject"),
        body=translate(
            "email.portfolio_ready.body",
            {
                "password_reset_address": app.config.get("AZURE_LOGIN_URL"),
                "username": username,
            },
        ),
    )


def make_initial_csp_data(portfolio):
    csp_data = portfolio.csp_data or {}
    return {
        **portfolio.to_dictionary(),
        **csp_data,
        "billing_account_name": app.config["AZURE_BILLING_ACCOUNT_NAME"],
    }


def do_provision_portfolio(csp: CloudProviderInterface, portfolio_id=None):
    portfolio = Portfolios.get_for_update(portfolio_id)
    fsm = Portfolios.get_or_create_state_machine(portfolio)
    app.logger.info("Triggering next transition for portfolio %s", portfolio.id)
    fsm.trigger_next_transition(csp_data=make_initial_csp_data(portfolio))
    if fsm.current_state == PortfolioStates.COMPLETED:
        send_ppoc_email(portfolio.to_dictionary())


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def provision_portfolio(self: Task, portfolio_id=None):
    do_provision_portfolio(app.csp.cloud, portfolio_id=portfolio_id)
    return portfolio_id


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def create_application(self: Task, application_id=None):
    do_create_application(app.csp.cloud, application_id=application_id)
    return application_id


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def create_user(self: Task, application_role_ids=None):
    do_create_user(app.csp.cloud, application_role_ids=application_role_ids)
    return application_role_ids


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def create_environment_role(self: Task, environment_role_id=None):
    do_create_environment_role(app.csp.cloud, environment_role_id=environment_role_id)
    return environment_role_id


@celery.task(bind=True, base=RecordFailure, autoretry_for=(GeneralCSPException,))
def create_environment(self: Task, environment_id=None):
    do_create_environment(app.csp.cloud, environment_id=environment_id)
    return environment_id


@celery.task(bind=True)
def dispatch_provision_portfolio(self: Task):
    """
    Iterate over portfolios with a corresponding State Machine that have not completed.
    """
    portfolio_ids = Portfolios.get_portfolios_pending_provisioning(
        pendulum.now(tz="UTC")
    )
    for portfolio_id in portfolio_ids:
        provision_portfolio.delay(portfolio_id=portfolio_id)
    return [str(portfolio_id) for portfolio_id in portfolio_ids]


@celery.task(bind=True)
def dispatch_create_application(self: Task):
    application_ids = Applications.get_applications_pending_creation()
    for application_id in application_ids:
        create_application.delay(application_id=application_id)
    return [str(application_id) for application_id in application_ids]


@celery.task(bind=True)
def dispatch_create_user(self: Task):
    application_role_id_groups = ApplicationRoles.get_pending_creation()
    for application_role_ids in application_role_id_groups:
        create_user.delay(application_role_ids=application_role_ids)
    return [[str(role_id) for role_id in group] for group in application_role_id_groups]


@celery.task(bind=True)
def dispatch_create_environment_role(self: Task):
    environment_role_ids = EnvironmentRoles.get_pending_creation()
    for environment_role_id in environment_role_ids:
        create_environment_role.delay(environment_role_id=environment_role_id)
    return [str(role_id) for role_id in environment_role_ids]


@celery.task(bind=True)
def dispatch_create_environment(self: Task):
    environment_ids = Environments.get_environments_pending_creation(
        pendulum.now(tz="UTC")
    )
    for environment_id in environment_ids:
        create_environment.delay(environment_id=environment_id)
    return [str(environment_id) for environment_id in environment_ids]


@celery.task(bind=True)
def send_task_order_files(self: Task):
    task_orders = TaskOrders.get_for_send_task_order_files()
    recipients = [app.config.get("MICROSOFT_TASK_ORDER_EMAIL_ADDRESS")]

    for task_order in task_orders:
        subject = translate(
            "email.task_order_sent.subject", {"to_number": task_order.number}
        )
        body = translate("email.task_order_sent.body", {"to_number": task_order.number})

        try:
            file = app.csp.files.download_task_order(task_order.pdf.object_name)
            file["maintype"] = "application"
            file["subtype"] = "pdf"
            send_mail(
                recipients=recipients, subject=subject, body=body, attachments=[file]
            )
        except (AzureError, SMTPException) as err:
            app.logger.exception(err)
            continue

        task_order.pdf_last_sent_at = pendulum.now(tz="UTC")
        db.session.add(task_order)

    db.session.commit()
    return [str(task_order.id) for task_order in task_orders]


@celery.task(bind=True)
def create_billing_instruction(self: Task):
    clins = TaskOrders.get_clins_for_create_billing_instructions()
    portfolio_ids = []

    for clin in clins:
        portfolio = clin.task_order.portfolio

        payload = BillingInstructionCSPPayload(
            tenant_id=portfolio.csp_data["tenant_id"],
            billing_account_name=app.config["AZURE_BILLING_ACCOUNT_NAME"],
            billing_profile_name=portfolio.csp_data["billing_profile_name"],
            initial_clin_amount=clin.obligated_amount,
            initial_clin_start_date=str(clin.start_date),
            initial_clin_end_date=str(clin.end_date),
            initial_clin_type=clin.jedi_clin_number,
            initial_task_order_id=str(clin.task_order_id),
        )

        try:
            app.csp.cloud.create_billing_instruction(payload)
        except (AzureError) as err:
            app.logger.exception(err)
            continue

        clin.last_sent_at = pendulum.now(tz="UTC")
        db.session.add(clin)
        portfolio_ids.append(portfolio.id)

    db.session.commit()

    return {
        "clin_ids": [str(clin.id) for clin in clins],
        "portfolio_ids": [str(portfolio_id) for portfolio_id in portfolio_ids],
    }
