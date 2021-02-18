import numbers

from flask import current_app as app
from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    DecimalField,
    FieldList,
    FormField,
    HiddenField,
    StringField,
)
from wtforms.fields.html5 import DateField
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from atat.forms.validators import alpha_numeric, number
from atat.utils.localization import translate

from .data import JEDI_CLIN_TYPES
from .fields import SelectField
from .forms import BaseForm, remove_empty_string

MAX_CLIN_AMOUNT = 1_000_000_000


def coerce_enum(enum_inst):
    if getattr(enum_inst, "value", None):
        return enum_inst.value
    else:
        return enum_inst


def validate_funding(form, field):
    if (
        isinstance(form.total_amount.data, numbers.Number)
        and isinstance(field.data, numbers.Number)
        and form.total_amount.data < field.data
    ):
        raise ValidationError(
            translate("forms.task_order.clin_funding_errors.obligated_amount_error")
        )


def validate_date_in_range(form, field):
    contract_start = app.config.get("CONTRACT_START_DATE")
    contract_end = app.config.get("CONTRACT_END_DATE")

    if field.data and (field.data < contract_start or field.data > contract_end):
        raise ValidationError(
            translate(
                "forms.task_order.pop_errors.range",
                {
                    "start": contract_start.strftime("%b %d, %Y"),
                    "end": contract_end.strftime("%b %d, %Y"),
                },
            )
        )


def remove_dashes(value):
    return value.replace("-", "") if value else None


def coerce_upper(value):
    return value.upper() if value else None


class CLINForm(FlaskForm):
    jedi_clin_type = SelectField(
        translate("task_orders.form.clin_type_label"),
        choices=JEDI_CLIN_TYPES,
        coerce=coerce_enum,
    )

    number = StringField(
        label=translate("task_orders.form.clin_number_label"),
        validators=[number(), Length(max=4)],
    )
    start_date = DateField(
        translate("task_orders.form.pop_start"),
        description=translate("task_orders.form.pop_example"),
        format="%m/%d/%Y",
        validators=[validate_date_in_range],
    )
    end_date = DateField(
        translate("task_orders.form.pop_end"),
        description=translate("task_orders.form.pop_example"),
        format="%m/%d/%Y",
        validators=[validate_date_in_range],
    )
    total_amount = DecimalField(
        label=translate("task_orders.form.total_funds_label"),
        validators=[
            NumberRange(
                0,
                MAX_CLIN_AMOUNT,
                translate("forms.task_order.clin_funding_errors.funding_range_error"),
            )
        ],
    )
    obligated_amount = DecimalField(
        label=translate("task_orders.form.obligated_funds_label"),
        validators=[
            validate_funding,
            NumberRange(
                0,
                MAX_CLIN_AMOUNT,
                translate("forms.task_order.clin_funding_errors.funding_range_error"),
            ),
        ],
    )

    def validate(self, *args, **kwargs):
        valid = super().validate(*args, **kwargs)

        if (
            self.start_date.data
            and self.end_date.data
            and self.start_date.data > self.end_date.data
        ):
            self.start_date.errors.append(
                translate("forms.task_order.pop_errors.date_order")
            )
            valid = False

        return valid


class AttachmentForm(BaseForm):
    filename = HiddenField(
        id="attachment_filename",
        validators=[
            Length(
                max=100, message=translate("forms.attachment.filename.length_error")
            ),
            alpha_numeric(),
        ],
    )
    object_name = HiddenField(
        id="attachment_object_name",
        validators=[
            Length(
                max=40, message=translate("forms.attachment.object_name.length_error")
            ),
            alpha_numeric(),
        ],
    )
    accept = ".pdf,application/pdf"

    def validate(self, *args, **kwargs):
        return super().validate(*args, **{**kwargs, "flash_invalid": False})


class TaskOrderForm(BaseForm):
    number = StringField(
        label=translate("forms.task_order.number_description"),
        filters=[remove_empty_string, remove_dashes, coerce_upper],
        validators=[alpha_numeric(), Length(min=13, max=17), Optional()],
    )
    pdf = FormField(AttachmentForm)
    clins = FieldList(FormField(CLINForm))


class SignatureForm(BaseForm):
    signature = BooleanField(
        translate("task_orders.sign.digital_signature_description"),
        validators=[DataRequired()],
    )
    confirm = BooleanField(
        translate("task_orders.sign.confirmation_description"),
        validators=[DataRequired()],
    )
