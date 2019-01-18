from wtforms.fields import (
    BooleanField,
    IntegerField,
    RadioField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
    FileField,
)
from wtforms.fields.html5 import DateField, TelField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import Required, Length

from atst.forms.validators import IsNumber, PhoneNumber, RequiredIf

from .forms import CacheableForm
from .data import (
    SERVICE_BRANCHES,
    APP_MIGRATION,
    APPLICATION_COMPLEXITY,
    DEV_TEAM,
    TEAM_EXPERIENCE,
    PERIOD_OF_PERFORMANCE_LENGTH,
)
from atst.utils.localization import translate


class AppInfoForm(CacheableForm):
    portfolio_name = StringField(
        translate("forms.task_order.portfolio_name_label"),
        description=translate("forms.task_order.portfolio_name_description"),
    )
    scope = TextAreaField(
        translate("forms.task_order.scope_label"),
        description=translate("forms.task_order.scope_description"),
    )
    defense_component = SelectField(
        translate("forms.task_order.defense_component_label"), choices=SERVICE_BRANCHES
    )
    app_migration = RadioField(
        translate("forms.task_order.app_migration.label"),
        description=translate("forms.task_order.app_migration.description"),
        choices=APP_MIGRATION,
        default="",
    )
    native_apps = RadioField(
        translate("forms.task_order.native_apps_label"),
        description=translate("forms.task_order.native_apps_description"),
        choices=[("yes", "Yes"), ("no", "No"), ("not_sure", "Not Sure")],
    )
    complexity = SelectMultipleField(
        translate("forms.task_order.complexity.label"),
        description=translate("forms.task_order.complexity.description"),
        choices=APPLICATION_COMPLEXITY,
        default="",
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    complexity_other = StringField(translate("forms.task_order.complexity_other_label"))
    dev_team = SelectMultipleField(
        translate("forms.task_order.dev_team.label"),
        description=translate("forms.task_order.dev_team.description"),
        choices=DEV_TEAM,
        default="",
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    dev_team_other = StringField(translate("forms.task_order.dev_team_other_label"))
    team_experience = RadioField(
        translate("forms.task_order.team_experience.label"),
        description=translate("forms.task_order.team_experience.description"),
        choices=TEAM_EXPERIENCE,
        default="",
    )


class FundingForm(CacheableForm):
    performance_length = SelectField(
        translate("forms.task_order.performance_length.label"),
        choices=PERIOD_OF_PERFORMANCE_LENGTH,
    )
    start_date = DateField(
        translate("forms.task_order.start_date_label"), format="%m/%d/%Y"
    )
    end_date = DateField(
        translate("forms.task_order.end_date_label"), format="%m/%d/%Y"
    )
    pdf = FileField(
        translate("forms.task_order.pdf_label"),
        description=translate("forms.task_order.pdf_description"),
    )
    clin_01 = IntegerField(translate("forms.task_order.clin_01_label"))
    clin_02 = IntegerField(translate("forms.task_order.clin_02_label"))
    clin_03 = IntegerField(translate("forms.task_order.clin_03_label"))
    clin_04 = IntegerField(translate("forms.task_order.clin_04_label"))


class UnclassifiedFundingForm(FundingForm):
    clin_02 = IntegerField(translate("forms.task_order.unclassified_clin_02_label"))
    clin_04 = IntegerField(translate("forms.task_order.unclassified_clin_04_label"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clin_02.data = "0"
        self.clin_04.data = "0"


class OversightForm(CacheableForm):
    ko_first_name = StringField(
        translate("forms.task_order.oversight_first_name_label")
    )
    ko_last_name = StringField(translate("forms.task_order.oversight_last_name_label"))
    ko_email = StringField(translate("forms.task_order.oversight_email_label"))
    ko_phone_number = TelField(
        translate("forms.task_order.oversight_phone_label"), validators=[PhoneNumber()]
    )
    ko_dod_id = StringField(
        translate("forms.task_order.oversight_dod_id_label"),
        validators=[RequiredIf("ko_invite"), Length(min=10), IsNumber()],
    )

    am_cor = BooleanField(translate("forms.task_order.oversight_am_cor_label"))
    cor_first_name = StringField(
        translate("forms.task_order.oversight_first_name_label")
    )
    cor_last_name = StringField(translate("forms.task_order.oversight_last_name_label"))
    cor_email = StringField(translate("forms.task_order.oversight_email_label"))
    cor_phone_number = TelField(
        translate("forms.task_order.oversight_phone_label"),
        validators=[RequiredIf("am_cor", False), PhoneNumber()],
    )
    cor_dod_id = StringField(
        translate("forms.task_order.oversight_dod_id_label"),
        validators=[RequiredIf("am_cor", False), Length(min=10), IsNumber()],
    )

    so_first_name = StringField(
        translate("forms.task_order.oversight_first_name_label")
    )
    so_last_name = StringField(translate("forms.task_order.oversight_last_name_label"))
    so_email = StringField(translate("forms.task_order.oversight_email_label"))
    so_phone_number = TelField(
        translate("forms.task_order.oversight_phone_label"), validators=[PhoneNumber()]
    )
    so_dod_id = StringField(
        translate("forms.task_order.oversight_dod_id_label"),
        validators=[Required(), Length(min=10), IsNumber()],
    )

    ko_invite = BooleanField(
        translate("forms.task_order.ko_invite_label"),
        description=translate("forms.task_order.skip_invite_description"),
    )
    cor_invite = BooleanField(
        translate("forms.task_order.cor_invite_label"),
        description=translate("forms.task_order.skip_invite_description"),
    )
    so_invite = BooleanField(
        translate("forms.task_order.so_invite_label"),
        description=translate("forms.task_order.skip_invite_description"),
    )


class ReviewForm(CacheableForm):
    pass
