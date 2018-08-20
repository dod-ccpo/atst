from wtforms.fields.html5 import IntegerField
from wtforms.fields import RadioField, TextAreaField
from wtforms.validators import Optional, Required

from .fields import DateField, SelectField
from .forms import ValidatedForm
from .data import SERVICE_BRANCHES
from atst.domain.requests import Requests


class RequestForm(ValidatedForm):

    def validate(self, *args, **kwargs):
        if self.jedi_migration.data == 'no':
            self.rationalization_software_systems.validators.append(Optional())
            self.technical_support_team.validators.append(Optional())
            self.organization_providing_assistance.validators.append(Optional())
            self.engineering_assessment.validators.append(Optional())
            self.data_transfers.validators.append(Optional())
            self.expected_completion_date.validators.append(Optional())
        elif self.jedi_migration.data == 'yes':
            if self.technical_support_team.data == 'no':
                self.organization_providing_assistance.validators.append(Optional())
            self.cloud_native.validators.append(Optional())

        try:
            annual_spend = int(self.estimated_monthly_spend.data or 0) * 12
        except ValueError:
            annual_spend = 0

        if annual_spend > Requests.AUTO_APPROVE_THRESHOLD:
            self.number_user_sessions.validators.append(Required())
            self.average_daily_traffic.validators.append(Required())

        return super(RequestForm, self).validate(*args, **kwargs)

    # Details of Use: General
    dod_component = SelectField(
        "DoD Component",
        description="Identify the DoD component that is requesting access to the JEDI Cloud",
        choices=SERVICE_BRANCHES,
        validators=[Required()]
    )

    jedi_usage = TextAreaField(
        "JEDI Usage",
        description="Your answer will help us provide tangible examples to DoD leadership how and why commercial cloud resources are accelerating the Department's missions",
        validators=[Required()]
    )


    # Details of Use: Cloud Readiness
    num_software_systems = IntegerField(
        "Number of Software Systems",
        description="Estimate the number of software systems that will be supported by this JEDI Cloud access request",
    )

    jedi_migration = RadioField(
        "JEDI Migration",
        description="Are you using the JEDI Cloud to migrate existing systems?",
        choices=[("yes", "Yes"), ("no", "No")],
        default="",
    )

    rationalization_software_systems = RadioField(
        description="Have you completed a “rationalization” of your software systems to move to the cloud?",
        choices=[("yes", "Yes"), ("no", "No"), ("In Progress", "In Progress")],
        default="",
    )

    technical_support_team = RadioField(
        description="Are you working with a technical support team experienced in cloud migrations?",
        choices=[("yes", "Yes"), ("no", "No")],
        default="",
    )

    organization_providing_assistance = RadioField(  # this needs to be updated to use checkboxes instead of radio
        description="If you are receiving migration assistance, what is the type of organization providing assistance?",
        choices=[
            ("In-house staff", "In-house staff"),
            ("Contractor", "Contractor"),
            ("Other DoD Organization", "Other DoD Organization"),
            ("None", "None"),
        ],
        default="",
    )

    engineering_assessment = RadioField(
        description="Have you completed an engineering assessment of your systems for cloud readiness?",
        choices=[("yes", "Yes"), ("no", "No"), ("In Progress", "In Progress")],
        default="",
    )

    data_transfers = SelectField(
        description="How much data is being transferred to the cloud?",
        choices=[
            ("", "Select an option"),
            ("Less than 100GB", "Less than 100GB"),
            ("100GB-500GB", "100GB-500GB"),
            ("500GB-1TB", "500GB-1TB"),
            ("1TB-50TB", "1TB-50TB"),
            ("50TB-100TB", "50TB-100TB"),
            ("100TB-500TB", "100TB-500TB"),
            ("500TB-1PB", "500TB-1PB"),
            ("1PB-5PB", "1PB-5PB"),
            ("5PB-10PB", "5PB-10PB"),
            ("Above 10PB", "Above 10PB"),
        ],
        validators=[Required()],
    )

    expected_completion_date = SelectField(
        description="When do you expect to complete your migration to the JEDI Cloud?",
        choices=[
            ("", "Select an option"),
            ("Less than 1 month", "Less than 1 month"),
            ("1-3 months", "1-3 months"),
            ("3-6 months", "3-6 months"),
            ("Above 12 months", "Above 12 months"),
        ],
        validators=[Required()],
    )

    cloud_native = RadioField(
        description="Are your software systems being developed cloud native?",
        choices=[("yes", "Yes"), ("no", "No")],
        default="",
    )

    # Details of Use: Financial Usage
    estimated_monthly_spend = IntegerField(
        "Estimated Monthly Spend",
        description='Use the <a href="#" target="_blank" class="icon-link">JEDI CSP Calculator</a> to estimate your <b>monthly</b> cloud resource usage and enter the dollar amount below. Note these estimates are for initial approval only. After the request is approved, you will be asked to provide a valid Task Order number with specific CLIN amounts for cloud services.',
    )

    dollar_value = IntegerField(
        "Total Spend",
        description="What is your total expected budget for this JEDI Cloud Request?",
    )

    number_user_sessions = IntegerField(
        description="How many user sessions do you expect on these systems each day?"
    )

    average_daily_traffic = IntegerField(
        "Average Daily Traffic (Number of Requests)",
        description="What is the average daily traffic you expect the systems under this cloud contract to use?"
    )

    average_daily_traffic_gb = IntegerField(
        "Average Daily Traffic (GB)",
        description="What is the average daily traffic you expect the systems under this cloud contract to use?"
    )

    start_date = DateField(
        description="When do you expect to start using the JEDI Cloud (not for billing purposes)?",
        validators=[
            Required()]
    )
