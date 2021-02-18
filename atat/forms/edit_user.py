from copy import deepcopy

from wtforms.fields import RadioField, StringField
from wtforms.fields.html5 import EmailField, TelField
from wtforms.validators import DataRequired, Email, Length, Optional

from atat.forms.validators import number
from atat.models.user import User
from atat.utils.localization import translate

from .data import SERVICE_BRANCHES
from .fields import SelectField
from .forms import BaseForm
from .validators import name, phone_number

SERVICE_BRANCH_CHOICES = [
    ("", translate("fragments.edit_user_form.service_choice"))
] + SERVICE_BRANCHES

USER_FIELDS = {
    "first_name": StringField(
        translate("forms.edit_user.first_name_label"),
        validators=[name(), Length(max=100)],
    ),
    "last_name": StringField(
        translate("forms.edit_user.last_name_label"),
        validators=[name(), Length(max=100)],
    ),
    "email": EmailField(translate("forms.edit_user.email_label"), validators=[Email()]),
    "phone_number": TelField(
        translate("forms.edit_user.phone_number_label"), validators=[phone_number()]
    ),
    "phone_ext": StringField("Extension", validators=[number(), Length(max=10)]),
    "service_branch": SelectField(
        translate("forms.edit_user.service_branch_label"),
        choices=SERVICE_BRANCH_CHOICES,
        default="",
    ),
    "citizenship": RadioField(
        choices=[
            ("United States", "United States"),
            ("Foreign National", "Foreign National"),
            ("Other", "Other"),
        ],
        default="",
    ),
    "designation": RadioField(
        translate("forms.edit_user.designation_label"),
        choices=[
            ("military", "Military"),
            ("civilian", "Civilian"),
            ("contractor", "Contractor"),
        ],
        default="",
    ),
}


def inherit_field(unbound_field, required=True):
    kwargs = deepcopy(unbound_field.kwargs)
    if not "validators" in kwargs:
        kwargs["validators"] = []

    if required:
        kwargs["validators"].append(DataRequired())
    else:
        kwargs["validators"].append(Optional())

    return unbound_field.field_class(*unbound_field.args, **kwargs)


def inherit_user_field(field_name):
    required = field_name in User.REQUIRED_FIELDS
    return inherit_field(USER_FIELDS[field_name], required=required)


class EditUserForm(BaseForm):

    first_name = inherit_user_field("first_name")
    last_name = inherit_user_field("last_name")
    email = inherit_user_field("email")
    phone_number = inherit_user_field("phone_number")
    phone_ext = inherit_user_field("phone_ext")
    service_branch = inherit_user_field("service_branch")
    citizenship = inherit_user_field("citizenship")
    designation = inherit_user_field("designation")
