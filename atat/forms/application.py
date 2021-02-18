from wtforms.fields import FieldList, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from atat.forms.validators import (
    alpha_numeric,
    list_item_required,
    list_items_unique,
    name,
)
from atat.utils.localization import translate

from .forms import BaseForm, remove_empty_string


class EditEnvironmentForm(BaseForm):
    name = StringField(
        label=translate("forms.environments.name_label"),
        validators=[DataRequired(), name(), Length(max=100)],
        filters=[remove_empty_string],
    )


class NameAndDescriptionForm(BaseForm):
    name = StringField(
        label=translate("forms.application.name_label"),
        validators=[DataRequired(), name(), Length(max=100)],
        filters=[remove_empty_string],
    )
    description = TextAreaField(
        label=translate("forms.application.description_label"),
        validators=[Optional(), Length(max=1_000)],
        filters=[remove_empty_string],
    )


class EnvironmentsForm(BaseForm):
    environment_names = FieldList(
        StringField(
            label=translate("forms.application.environment_names_label"),
            filters=[remove_empty_string],
            validators=[alpha_numeric(), Length(max=100)],
        ),
        validators=[
            list_item_required(
                message=translate(
                    "forms.application.environment_names_required_validation_message"
                )
            ),
            list_items_unique(
                message=translate(
                    "forms.application.environment_names_unique_validation_message"
                )
            ),
        ],
    )
