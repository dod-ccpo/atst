from wtforms.fields import SelectMultipleField, StringField, TextAreaField
from wtforms.validators import InputRequired, Length
from wtforms.widgets import CheckboxInput, ListWidget

from atat.forms.validators import name
from atat.utils.localization import translate

from .data import SERVICE_BRANCHES
from .forms import BaseForm


class PortfolioForm(BaseForm):
    name = StringField(
        translate("forms.portfolio.name.label"),
        validators=[
            Length(
                min=4,
                max=100,
                message=translate("forms.portfolio.name.length_validation_message"),
            ),
            name(),
        ],
    )
    description = TextAreaField(
        translate("forms.portfolio.description.label"), validators=[Length(max=1_000)]
    )


class PortfolioCreationForm(PortfolioForm):
    defense_component = SelectMultipleField(
        translate("forms.portfolio.defense_component.title"),
        description=translate("forms.portfolio.defense_component.help_text"),
        choices=SERVICE_BRANCHES,
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
        validators=[
            InputRequired(
                message=translate(
                    "forms.portfolio.defense_component.validation_message"
                )
            )
        ],
    )
