import re
from enum import Enum
from secrets import token_urlsafe
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, root_validator, validator

from atat.utils import camel_to_snake, snake_to_camel

from .utils import generate_mail_nickname, generate_user_principal_name

AZURE_MGMNT_PATH = "/providers/Microsoft.Management/managementGroups/"

MANAGEMENT_GROUP_NAME_REGEX = "^[a-zA-Z0-9\-_\(\)\.]+$"

SUBSCRIPTION_ID_REGEX = re.compile(
    "\/?subscriptions\/([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})",
    re.I,
)
PAYLOAD_CLASS_SUFFIX_REGEX = re.compile(r"(Creation|Verification)?CSP.*")


def stage_to_classname(stage):
    return "".join(map(lambda word: word.capitalize(), stage.split("_")))


def class_to_stage(klass):
    """Given a CSP model class, derive the stage name

    Args:
        klass (pydantic.BaseModel): a pydantic CSP data model class

    Returns:
        str: the stage name
    """
    class_name = klass.__name__
    stage_camel_case = PAYLOAD_CLASS_SUFFIX_REGEX.split(class_name)[0]
    return camel_to_snake(stage_camel_case)


def normalize_management_group_id(cls, id_):
    if id_:
        if AZURE_MGMNT_PATH not in id_:
            return f"{AZURE_MGMNT_PATH}{id_}"
        else:
            return id_


class AliasModel(BaseModel):
    """
    This provides automatic camel <-> snake conversion for serializing to/from json
    You can override the alias generation in subclasses by providing a Config that defines
    a fields property with a dict mapping variables to their cast names, for cases like:
    * some_url:someURL
    * user_object_id:objectId
    """

    reset_stage: bool = False

    class Config:
        alias_generator = snake_to_camel
        allow_population_by_field_name = True

    def dict(self, *args, **kwargs):
        kwargs.setdefault("exclude")
        if kwargs["exclude"] is None:
            kwargs["exclude"] = set()
        kwargs["exclude"].update({"reset_stage"})
        return super().dict(*args, **kwargs)


class BaseCSPPayload(AliasModel):
    tenant_id: str


class TenantCSPPayload(AliasModel):
    user_id: str
    password: Optional[str]
    domain_name: str
    first_name: str
    last_name: str
    country_code: str
    password_recovery_email_address: str


class PrincipalTokenPayload(BaseModel):
    scope: str
    client_id: str


class UserPrincipalTokenPayload(PrincipalTokenPayload):
    grant_type = "password"
    username: str
    password: str


class ServicePrincipalTokenPayload(PrincipalTokenPayload):
    grant_type = "client_credentials"
    client_secret: str


class TenantCSPResult(AliasModel):
    user_id: str
    tenant_id: str
    user_object_id: str
    domain_name: str

    tenant_admin_username: Optional[str]
    tenant_admin_password: Optional[str]

    class Config:
        fields = {
            "user_object_id": "objectId",
        }

    def dict(self, *args, **kwargs):
        exclude = {"tenant_admin_username", "tenant_admin_password"}
        if "exclude" not in kwargs:
            kwargs["exclude"] = exclude
        else:
            kwargs["exclude"].update(exclude)

        return super().dict(*args, **kwargs)

    def get_creds(self):
        return {
            "tenant_admin_username": self.tenant_admin_username,
            "tenant_admin_password": self.tenant_admin_password,
            "tenant_id": self.tenant_id,
        }


class BillingProfileAddress(AliasModel):
    company_name: str
    address_line_1: str
    city: str
    region: str
    country: str
    postal_code: str


class BillingProfileCLINBudget(AliasModel):
    clin_budget: Dict
    """
        "clinBudget": {
            "amount": 0,
            "startDate": "2019-12-18T16:47:40.909Z",
            "endDate": "2019-12-18T16:47:40.909Z",
            "externalReferenceId": "string"
        }
    """


class BillingProfileCreationCSPPayload(BaseCSPPayload):
    tenant_id: str
    billing_profile_display_name: str
    billing_account_name: str
    enabled_azure_plans: Optional[List[str]]
    address: BillingProfileAddress

    @validator("enabled_azure_plans", pre=True, always=True)
    def default_enabled_azure_plans(cls, v):
        """
        Normally you'd implement this by setting the field with a value of:
            dataclasses.field(default_factory=list)
        but that prevents the object from being correctly pickled, so instead we need
        to rely on a validator to ensure this has an empty value when not specified
        """
        return v or []

    class Config:
        fields = {"billing_profile_display_name": "displayName"}


class BillingProfileCreationCSPResult(AliasModel):
    billing_profile_verify_url: str
    billing_profile_retry_after: int

    class Config:
        fields = {
            "billing_profile_verify_url": "Location",
            "billing_profile_retry_after": "Retry-After",
        }


class BillingProfileVerificationCSPPayload(BaseCSPPayload):
    billing_profile_verify_url: str


class BillingInvoiceSection(AliasModel):
    invoice_section_id: str
    invoice_section_name: str

    class Config:
        fields = {"invoice_section_id": "id", "invoice_section_name": "name"}


class BillingProfileProperties(AliasModel):
    address: BillingProfileAddress
    billing_profile_display_name: str
    invoice_sections: List[BillingInvoiceSection]

    class Config:
        fields = {"billing_profile_display_name": "displayName"}


class BillingProfileVerificationCSPResult(AliasModel):
    billing_profile_id: str
    billing_profile_name: str
    billing_profile_properties: BillingProfileProperties

    class Config:
        fields = {
            "billing_profile_id": "id",
            "billing_profile_name": "name",
            "billing_profile_properties": "properties",
        }


class BillingProfileTenantAccessCSPPayload(BaseCSPPayload):
    tenant_id: str
    user_object_id: str
    billing_account_name: str
    billing_profile_name: str


class BillingProfileTenantAccessCSPResult(AliasModel):
    billing_role_assignment_id: str
    billing_role_assignment_name: str

    class Config:
        fields = {
            "billing_role_assignment_id": "id",
            "billing_role_assignment_name": "name",
        }


class PrincipalAppGraphApiPermissionsCSPPayload(BaseCSPPayload):
    principal_id: str


class PrincipalAppGraphApiPermissionsCSPResult(AliasModel):
    pass


class TaskOrderBillingCreationCSPPayload(BaseCSPPayload):
    billing_account_name: str
    billing_profile_name: str


class TaskOrderBillingCreationCSPResult(AliasModel):
    task_order_billing_verify_url: str
    task_order_retry_after: int

    class Config:
        fields = {
            "task_order_billing_verify_url": "Location",
            "task_order_retry_after": "Retry-After",
        }


class TaskOrderBillingVerificationCSPPayload(BaseCSPPayload):
    task_order_billing_verify_url: str


class BillingProfileEnabledPlanDetails(AliasModel):
    enabled_azure_plans: List[Dict]


class TaskOrderBillingVerificationCSPResult(AliasModel):
    billing_profile_id: str
    billing_profile_name: str
    billing_profile_enabled_plan_details: BillingProfileEnabledPlanDetails

    class Config:
        fields = {
            "billing_profile_id": "id",
            "billing_profile_name": "name",
            "billing_profile_enabled_plan_details": "properties",
        }


class BillingInstructionCSPPayload(BaseCSPPayload):
    initial_clin_amount: float
    initial_clin_start_date: str
    initial_clin_end_date: str
    initial_clin_type: str
    initial_task_order_id: str
    billing_account_name: str
    billing_profile_name: str


class BillingInstructionCSPResult(AliasModel):
    reported_clin_name: str

    class Config:
        fields = {
            "reported_clin_name": "name",
        }


class RoleAssignmentPayload(BaseModel):
    role_definition_scope: str
    role_definition_name: str
    role_assignment_scope: str
    role_assignment_name = str(uuid4())
    principal_id: str

    @property
    def role_definition_id(self):
        return (
            self.role_definition_scope
            + "/providers/Microsoft.Authorization/roleDefinitions/"
            + self.role_definition_name
        )


class TenantAdminOwnershipCSPPayload(BaseCSPPayload):
    root_management_group_name: str
    user_object_id: str

    class Config:
        fields = {"root_management_group_name": "tenant_id"}


class TenantAdminOwnershipCSPResult(AliasModel):
    admin_owner_assignment_id: str

    class Config:
        fields = {"admin_owner_assignment_id": "id"}


class TenantAdminCredentialResetCSPPayload(BaseCSPPayload):
    user_object_id: str
    new_password: Optional[str]


class TenantAdminCredentialResetCSPResult(AliasModel):
    pass


class TenantPrincipalOwnershipCSPPayload(BaseCSPPayload):
    root_management_group_name: str
    user_object_id: str
    principal_id: str

    class Config:
        fields = {"root_management_group_name": "tenant_id"}


class TenantPrincipalOwnershipCSPResult(AliasModel):
    principal_owner_assignment_id: str

    class Config:
        fields = {"principal_owner_assignment_id": "id"}


class TenantPrincipalAppCSPPayload(BaseCSPPayload):
    display_name: str
    tenant_principal_app_display_name = "ATAT Remote Admin"


class TenantPrincipalAppCSPResult(AliasModel):
    principal_app_id: str
    principal_app_object_id: str

    class Config:
        fields = {"principal_app_id": "appId", "principal_app_object_id": "id"}


class TenantPrincipalCSPPayload(BaseCSPPayload):
    principal_app_id: str


class TenantPrincipalCSPResult(AliasModel):
    principal_id: str

    class Config:
        fields = {"principal_id": "id"}


class TenantPrincipalCredentialCSPPayload(BaseCSPPayload):
    principal_app_id: str
    principal_app_object_id: str


class TenantPrincipalCredentialCSPResult(AliasModel):
    principal_client_id: str
    principal_creds_established: bool


class AdminRoleDefinitionCSPPayload(BaseCSPPayload):
    pass


class AdminRoleDefinitionCSPResult(AliasModel):
    admin_role_def_id: str


class PrincipalAdminRoleCSPPayload(BaseCSPPayload):
    principal_id: str
    admin_role_def_id: str


class PrincipalAdminRoleCSPResult(AliasModel):
    principal_assignment_id: str

    class Config:
        fields = {"principal_assignment_id": "id"}


class ManagementGroupCSPPayload(BaseCSPPayload):
    """
    :param: management_group_name: Just pass a UUID for this.
    :param: display_name: This can contain any character and
        spaces, but should be 90 characters or fewer long.
    :param: parent_id: This should be the fully qualified Azure ID,
        i.e. /providers/Microsoft.Management/managementGroups/[management group ID]
    """

    management_group_name: Optional[str]
    display_name: str
    parent_id: Optional[str]

    _normalize_parent_id = validator("parent_id", allow_reuse=True)(
        normalize_management_group_id
    )

    @validator("management_group_name", pre=True, always=True)
    def supply_management_group_name_default(cls, name):
        if name:
            if re.match(MANAGEMENT_GROUP_NAME_REGEX, name) is None:
                raise ValueError(
                    f"Management group name must match {MANAGEMENT_GROUP_NAME_REGEX}"
                )

            return name[0:90]
        else:
            return str(uuid4())

    @validator("display_name", pre=True, always=True)
    def enforce_display_name_length(cls, name):
        return name[0:90]


class ManagementGroupCSPResponse(AliasModel):
    id: str
    name: str


class ManagementGroupGetCSPPayload(BaseCSPPayload):
    management_group_name: str


class ManagementGroupGetCSPResponse(AliasModel):
    id: str


class ApplicationCSPPayload(ManagementGroupCSPPayload):
    class Config:
        fields = {
            "root_management_group_name": "tenant_id",
        }


class ApplicationCSPResult(ManagementGroupCSPResponse):
    pass


class InitialMgmtGroupCSPPayload(ManagementGroupCSPPayload):
    pass


class InitialMgmtGroupCSPResult(AliasModel):
    initial_management_group_name: str

    class Config:
        fields = {
            "initial_management_group_name": "name",
        }

    @property
    def initial_management_group_id(self):
        return f"/providers/Microsoft.Management/managementGroups/{self.initial_management_group_name}"


class InitialMgmtGroupVerificationCSPPayload(ManagementGroupGetCSPPayload):
    user_object_id: str

    class Config:
        fields = {"management_group_name": "initial_management_group_name"}


class InitialMgmtGroupVerificationCSPResult(ManagementGroupGetCSPResponse):
    pass


class EnvironmentCSPPayload(ManagementGroupCSPPayload):
    pass


class EnvironmentCSPResult(ManagementGroupCSPResponse):
    pass


class KeyVaultCredentials(BaseModel):
    root_sp_client_id: Optional[str]
    root_sp_key: Optional[str]
    root_tenant_id: Optional[str]

    tenant_id: Optional[str]

    tenant_admin_username: Optional[str]
    tenant_admin_password: Optional[str]

    tenant_sp_client_id: Optional[str]
    tenant_sp_key: Optional[str]

    @root_validator(pre=True)
    def enforce_admin_creds(cls, values):
        tenant_id = values.get("tenant_id")
        username = values.get("tenant_admin_username")
        password = values.get("tenant_admin_password")
        if any([username, password]) and not all([tenant_id, username, password]):
            raise ValueError(
                "tenant_id, tenant_admin_username, and tenant_admin_password must all be set if any one is"
            )

        return values

    @root_validator(pre=True)
    def enforce_sp_creds(cls, values):
        tenant_id = values.get("tenant_id")
        client_id = values.get("tenant_sp_client_id")
        key = values.get("tenant_sp_key")
        if any([client_id, key]) and not all([tenant_id, client_id, key]):
            raise ValueError(
                "tenant_id, tenant_sp_client_id, and tenant_sp_key must all be set if any one is"
            )

        return values

    @root_validator(pre=True)
    def enforce_root_creds(cls, values):
        sp_creds = [
            values.get("root_tenant_id"),
            values.get("root_sp_client_id"),
            values.get("root_sp_key"),
        ]
        if any(sp_creds) and not all(sp_creds):
            raise ValueError(
                "root_tenant_id, root_sp_client_id, and root_sp_key must all be set if any one is"
            )

        return values

    def merge_credentials(
        self, new_creds: "KeyVaultCredentials"
    ) -> "KeyVaultCredentials":
        updated_creds = {k: v for k, v in new_creds.dict().items() if v}
        old_creds = self.dict()
        old_creds.update(updated_creds)

        return KeyVaultCredentials(**old_creds)


class SubscriptionCreationCSPPayload(BaseCSPPayload):
    display_name: str
    parent_group_id: str
    billing_account_name: str
    billing_profile_name: str
    invoice_section_name: str


class SubscriptionCreationCSPResult(AliasModel):
    subscription_verify_url: str
    subscription_retry_after: int

    class Config:
        fields = {
            "subscription_verify_url": "Location",
            "subscription_retry_after": "Retry-After",
        }


class SubscriptionVerificationCSPPayload(BaseCSPPayload):
    subscription_verify_url: str


class SuscriptionVerificationCSPResult(AliasModel):
    subscription_id: str

    @validator("subscription_id", pre=True, always=True)
    def enforce_display_name_length(cls, sub_id):
        sub_id_match = SUBSCRIPTION_ID_REGEX.match(sub_id)
        if sub_id_match:
            return sub_id_match.group(1)

        return False

    class Config:
        fields = {"subscription_id": "subscriptionLink"}


class ProductPurchaseCSPPayload(BaseCSPPayload):
    billing_account_name: str
    billing_profile_name: str


class ProductPurchaseCSPResult(AliasModel):
    product_purchase_verify_url: str
    product_purchase_retry_after: int

    class Config:
        fields = {
            "product_purchase_verify_url": "Location",
            "product_purchase_retry_after": "Retry-After",
        }


class ProductPurchaseVerificationCSPPayload(BaseCSPPayload):
    product_purchase_verify_url: str


class ProductPurchaseVerificationCSPResult(AliasModel):
    premium_purchase_date: str

    @root_validator(pre=True)
    def populate_premium_purchase_date(cls, values):
        if "premium_purchase_date" in values:
            return values
        try:
            values["premium_purchase_date"] = values["properties"]["purchaseDate"]
            return values
        except KeyError:
            raise ValueError("Premium purchasedate not present in payload")


class UserMixin(BaseModel):
    password: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]

    @property
    def user_principal_name(self):
        return generate_user_principal_name(self.display_name, self.tenant_host_name)

    @property
    def mail_nickname(self):
        return generate_mail_nickname(self.display_name)

    @validator("password", pre=True, always=True)
    def supply_password_default(cls, password):
        return password or token_urlsafe(16)


class UserCSPPayload(BaseCSPPayload, UserMixin):
    display_name: str
    tenant_host_name: str
    email: str


class UserCSPResult(AliasModel):
    id: str


class UserRoleCSPPayload(BaseCSPPayload):
    class Roles(str, Enum):
        owner = "owner"
        contributor = "contributor"
        billing = "billing"

    management_group_id: str
    role: Roles
    user_object_id: str

    _normalize_management_group_id = validator("management_group_id", allow_reuse=True)(
        normalize_management_group_id
    )


class UserRoleCSPResult(AliasModel):
    id: str


class QueryColumn(AliasModel):
    name: str
    type: str


class CostManagementQueryProperties(AliasModel):
    columns: List[QueryColumn]
    rows: List[Optional[list]]


class CostManagementQueryCSPResult(AliasModel):
    name: str
    properties: CostManagementQueryProperties


class CostManagementQueryCSPPayload(BaseCSPPayload):
    invoice_section_id: str
    from_date: str
    to_date: str

    @root_validator(pre=True)
    def populate_invoice_section_id(cls, values):
        if "invoice_section_id" in values:
            return values
        try:
            values["invoice_section_id"] = values["billing_profile_properties"][
                "invoice_sections"
            ][0]["invoice_section_id"]
            return values
        except (KeyError, IndexError):
            raise ValueError("Invoice section ID not present in payload")


class BillingOwnerCSPPayload(BaseCSPPayload, UserMixin):
    """
    This class needs to consume data in the shape it's in from the
    top-level portfolio CSP data, but return it in the shape
    needed for user provisioning.
    """

    display_name = "billing_admin"
    domain_name: str
    password_recovery_email_address: str

    @property
    def tenant_host_name(self):
        return self.domain_name

    @property
    def email(self):
        return self.password_recovery_email_address


class BillingOwnerCSPResult(AliasModel):
    billing_owner_id: str


class PoliciesCSPPayload(BaseCSPPayload):
    root_management_group_name: str
    tenant_id: str

    class Config:
        fields = {"root_management_group_name": "tenant_id"}


class PoliciesCSPResult(AliasModel):
    policy_assignment_id: str

    class Config:
        fields = {"policy_assignment_id": "id"}


__all__ = [
    "AdminRoleDefinitionCSPPayload",
    "AdminRoleDefinitionCSPResult",
    "ApplicationCSPPayload",
    "ApplicationCSPResult",
    "BillingInstructionCSPPayload",
    "BillingInstructionCSPResult",
    "BillingOwnerCSPPayload",
    "BillingOwnerCSPResult",
    "BillingProfileCreationCSPPayload",
    "BillingProfileCreationCSPResult",
    "BillingProfileTenantAccessCSPPayload",
    "BillingProfileTenantAccessCSPResult",
    "BillingProfileVerificationCSPPayload",
    "BillingProfileVerificationCSPResult",
    "CostManagementQueryCSPPayload",
    "CostManagementQueryCSPResult",
    "EnvironmentCSPPayload",
    "EnvironmentCSPResult",
    "InitialMgmtGroupCSPPayload",
    "InitialMgmtGroupCSPResult",
    "InitialMgmtGroupVerificationCSPPayload",
    "InitialMgmtGroupVerificationCSPResult",
    "KeyVaultCredentials",
    "ManagementGroupCSPPayload",
    "ManagementGroupCSPResponse",
    "ManagementGroupGetCSPPayload",
    "ManagementGroupGetCSPResponse",
    "PoliciesCSPPayload",
    "PoliciesCSPResult",
    "PrincipalAdminRoleCSPPayload",
    "PrincipalAdminRoleCSPResult",
    "PrincipalAppGraphApiPermissionsCSPPayload",
    "PrincipalAppGraphApiPermissionsCSPResult",
    "ProductPurchaseCSPPayload",
    "ProductPurchaseCSPResult",
    "ProductPurchaseVerificationCSPPayload",
    "ProductPurchaseVerificationCSPResult",
    "SubscriptionCreationCSPPayload",
    "SubscriptionCreationCSPResult",
    "SubscriptionVerificationCSPPayload",
    "SuscriptionVerificationCSPResult",
    "TaskOrderBillingCreationCSPPayload",
    "TaskOrderBillingCreationCSPResult",
    "TaskOrderBillingVerificationCSPPayload",
    "TaskOrderBillingVerificationCSPResult",
    "TenantAdminCredentialResetCSPPayload",
    "TenantAdminCredentialResetCSPResult",
    "TenantAdminOwnershipCSPPayload",
    "TenantAdminOwnershipCSPResult",
    "TenantCSPPayload",
    "TenantCSPResult",
    "TenantPrincipalAppCSPPayload",
    "TenantPrincipalAppCSPResult",
    "TenantPrincipalCredentialCSPPayload",
    "TenantPrincipalCredentialCSPResult",
    "TenantPrincipalCSPPayload",
    "TenantPrincipalCSPResult",
    "TenantPrincipalOwnershipCSPPayload",
    "TenantPrincipalOwnershipCSPResult",
    "UserCSPPayload",
    "UserCSPResult",
    "UserRoleCSPPayload",
    "UserRoleCSPResult",
]
