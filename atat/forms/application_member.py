from flask_wtf import FlaskForm
from wtforms import Form
from wtforms.fields import BooleanField, FieldList, FormField, HiddenField
from wtforms.validators import UUID, Length

from atat.domain.permission_sets import PermissionSets
from atat.forms.fields import SelectField
from atat.forms.validators import alpha_numeric
from atat.utils.localization import translate

from .data import ENV_ROLE_NO_ACCESS as NO_ACCESS
from .data import ENV_ROLES
from .member import NewForm as BaseNewMemberForm


class EnvironmentForm(Form):
    environment_id = HiddenField(validators=[UUID()])
    environment_name = HiddenField(validators=[alpha_numeric(), Length(max=100)])
    role = SelectField(
        environment_name,
        choices=ENV_ROLES,
        default=NO_ACCESS,
        filters=[lambda x: NO_ACCESS if x == "None" else x],
    )
    disabled = BooleanField("Revoke Access", default=False)

    @property
    def data(self):
        _data = super().data
        if "role" in _data and _data["role"] == NO_ACCESS:
            _data["role"] = None
        return _data


class PermissionsForm(FlaskForm):
    perms_env_mgmt = BooleanField(
        translate("portfolios.applications.members.form.env_mgmt.label"),
        default=False,
        description=translate(
            "portfolios.applications.members.form.env_mgmt.description"
        ),
    )
    perms_team_mgmt = BooleanField(
        translate("portfolios.applications.members.form.team_mgmt.label"),
        default=False,
        description=translate(
            "portfolios.applications.members.form.team_mgmt.description"
        ),
    )

    @property
    def data(self):
        _data = super().data
        _data.pop("csrf_token", None)
        perm_sets = []

        if _data["perms_env_mgmt"]:
            perm_sets.append(PermissionSets.EDIT_APPLICATION_ENVIRONMENTS)

        if _data["perms_team_mgmt"]:
            perm_sets.append(PermissionSets.EDIT_APPLICATION_TEAM)

        _data["permission_sets"] = perm_sets
        return _data


class NewForm(PermissionsForm):
    user_data = FormField(BaseNewMemberForm)
    environment_roles = FieldList(FormField(EnvironmentForm))


class UpdateMemberForm(PermissionsForm):
    environment_roles = FieldList(FormField(EnvironmentForm))
