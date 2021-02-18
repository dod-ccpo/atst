from flask_wtf import FlaskForm
from wtforms.fields import StringField
from wtforms.fields.html5 import EmailField, TelField
from wtforms.validators import DataRequired, Email, Length, Optional

from atat.forms.validators import name, number, phone_number
from atat.utils.localization import translate


class NewForm(FlaskForm):
    first_name = StringField(
        label=translate("forms.new_member.first_name_label"),
        validators=[DataRequired(), name(), Length(max=100)],
    )
    last_name = StringField(
        label=translate("forms.new_member.last_name_label"),
        validators=[DataRequired(), name(), Length(max=100)],
    )
    email = EmailField(
        translate("forms.new_member.email_label"), validators=[DataRequired(), Email()]
    )
    phone_number = TelField(
        translate("forms.new_member.phone_number_label"),
        validators=[Optional(), phone_number()],
    )
    phone_ext = StringField("Extension", validators=[number(), Length(max=10)])
    dod_id = StringField(
        translate("forms.new_member.dod_id_label"),
        validators=[DataRequired(), Length(min=10), number()],
    )
