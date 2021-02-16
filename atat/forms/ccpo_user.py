from flask_wtf import FlaskForm
from wtforms.fields import StringField
from wtforms.validators import DataRequired, Length

from atat.forms.validators import number
from atat.utils.localization import translate


class CCPOUserForm(FlaskForm):
    dod_id = StringField(
        translate("forms.new_member.dod_id_label"),
        validators=[DataRequired(), Length(min=10, max=10), number()],
    )
