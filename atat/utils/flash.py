"""
Supports user feedback via Flask Message Flashing.
See https://flask.palletsprojects.com/en/1.1.x/patterns/flashing/
"""
from flask import flash

from atat.utils.localization import translate

_FLASH_SUCCESS = "flash.success"

MESSAGES = {
    "application_created": {
        "title": "flash.application.created.title",
        "message": "flash.application.created.message",
        "category": "success",
    },
    "application_updated": {
        "title": _FLASH_SUCCESS,
        "message": "flash.application.updated",
        "category": "success",
    },
    "application_environments_name_error": {
        "title": None,
        "message": "flash.application.env_name_error.message",
        "category": "error",
    },
    "application_environments_updated": {
        "title": "flash.environment.updated.title",
        "message": "flash.environment.updated.message",
        "category": "success",
    },
    "application_invite_error": {
        "title": "flash.application_invite.error.title",
        "message": "flash.application_invite.error.message",
        "category": "error",
    },
    "application_invite_resent": {
        "title": None,
        "message": "flash.application_invite.resent.message",
        "category": "success",
    },
    "application_member_removed": {
        "title": "flash.application_member.removed.title",
        "message": "flash.application_member.removed.message",
        "category": "success",
    },
    "application_member_update_error": {
        "title": "flash.application_member.update_error.title",
        "message": "flash.application_member.update_error.message",
        "category": "error",
    },
    "application_member_updated": {
        "title": "flash.application_member.updated.title",
        "message": "flash.application_member.updated.message",
        "category": "success",
    },
    "application_name_error": {
        "title": None,
        "message": "flash.application.name_error.message",
        "category": "error",
    },
    "ccpo_user_added": {
        "title": _FLASH_SUCCESS,
        "message": "flash.ccpo_user.added.message",
        "category": "success",
    },
    "ccpo_user_not_found": {
        "title": "ccpo.form.user_not_found_title",
        "message": "ccpo.form.user_not_found_text",
        "category": "info",
    },
    "ccpo_user_removed": {
        "title": _FLASH_SUCCESS,
        "message": "flash.ccpo_user.removed.message",
        "category": "success",
    },
    "environment_added": {
        "title": _FLASH_SUCCESS,
        "message": "flash.environment_added",
        "category": "success",
    },
    "environment_deleted": {
        "title": "flash.environment.deleted.title",
        "message": "flash.environment.deleted.message",
        "category": "success",
    },
    "environment_subscription_failure": {
        "title": "flash.environment.subscription_failure.title",
        "message": "flash.environment.subscription_failure.message",
        "category": "error",
    },
    "environment_subscription_success": {
        "title": "flash.environment.subscription_success.title",
        "message": "flash.environment.subscription_success.message",
        "category": "success",
    },
    "form_errors": {
        "title": "flash.form.errors.title",
        "message": "flash.form.errors.message",
        "category": "error",
    },
    "insufficient_funds": {
        "title": "flash.task_order.insufficient_funds.title",
        "message": None,
        "category": "warning",
    },
    "invite_revoked": {
        "title": "flash.invite_revoked.title",
        "message": "flash.invite_revoked.message",
        "category": "success",
    },
    "logged_out": {
        "title": "flash.logged_out.title",
        "message": "flash.logged_out.message",
        "category": "info",
    },
    "login_next": {
        "title": "flash.login_required_title",
        "message": "flash.login_required_message",
        "category": "warning",
    },
    "new_application_member": {
        "title": "flash.new_application_member.title",
        "message": "flash.new_application_member.message",
        "category": "success",
    },
    "new_portfolio_member": {
        "title": "flash.new_portfolio_member.title",
        "message": "flash.new_portfolio_member.message",
        "category": "success",
    },
    "portfolio_member_removed": {
        "title": "flash.deleted_member",
        "message": "flash.delete_member_success",
        "category": "success",
    },
    "primary_point_of_contact_changed": {
        "title": "flash.new_ppoc_title",
        "message": "flash.new_ppoc_message",
        "category": "success",
    },
    "resend_portfolio_invitation": {
        "title": None,
        "message": "flash.portfolio_invite.resent.message",
        "category": "success",
    },
    "resend_portfolio_invitation_error": {
        "title": "flash.portfolio_invite.error.title",
        "message": "flash.portfolio_invite.error.message",
        "category": "error",
    },
    "revoked_portfolio_access": {
        "title": "flash.portfolio_member.revoked.title",
        "message": "flash.portfolio_member.revoked.message",
        "category": "success",
    },
    "session_expired": {
        "title": "flash.session_expired.title",
        "message": "flash.session_expired.message",
        "category": "error",
    },
    "task_order_draft": {
        "title": "task_orders.form.draft_alert_title",
        "message": "task_orders.form.draft_alert_message",
        "category": "warning",
    },
    "task_order_number_error": {
        "title": None,
        "message": "flash.task_order_number_error.message",
        "category": "error",
    },
    "task_order_submitted": {
        "title": "flash.task_order.submitted.title",
        "message": "flash.task_order.submitted.message",
        "category": "success",
    },
    "update_portfolio_member": {
        "title": "flash.portfolio_member.update.title",
        "message": "flash.portfolio_member.update.message",
        "category": "success",
    },
    "update_portfolio_member_error": {
        "title": "flash.portfolio_member.update_error.title",
        "message": "flash.portfolio_member.update_error.message",
        "category": "error",
    },
    "updated_application_team_settings": {
        "title": _FLASH_SUCCESS,
        "message": "flash.updated_application_team_settings",
        "category": "success",
    },
    "user_must_complete_profile": {
        "title": "flash.user.complete_profile.title",
        "message": "flash.user.complete_profile.message",
        "category": "info",
    },
    "user_updated": {
        "title": "flash.user.updated.title",
        "message": None,
        "category": "success",
    },
}


def formatted_flash(message_name, **message_args):
    config = MESSAGES[message_name]

    title = translate(config["title"], message_args) if config["title"] else None
    message = translate(config["message"], message_args) if config["message"] else None
    actions = (
        translate(config["actions"], message_args) if config.get("actions") else None
    )

    flash({"title": title, "message": message, "actions": actions}, config["category"])
