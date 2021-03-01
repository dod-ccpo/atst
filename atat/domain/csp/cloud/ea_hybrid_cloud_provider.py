from atat.domain.csp.cloud.azure_cloud_provider import AzureCloudProvider
from atat.domain.csp.cloud.hybrid_cloud_provider import HybridCloudProvider
from atat.domain.csp.cloud.mock_cloud_provider import MockCloudProvider
from atat.domain.csp.cloud.models import (
    BillingOwnerCSPPayload,
    BillingOwnerCSPResult,
    CostManagementQueryCSPPayload,
)


class EaHybridCloudProvider(HybridCloudProvider):
    """
        This is the provider made to be used under an EA specific environment.

        Implements py:class::HybridCloudProvider
    """

    HYBRID_PREFIX = "EA-Hybrid ::"

    def __init__(self, azure: AzureCloudProvider, mock: MockCloudProvider, config):
        super().__init__(azure, mock, config)

    def get_reporting_data(self, payload: CostManagementQueryCSPPayload):
        return self.mock.get_reporting_data(payload)

    def create_billing_owner(
        self, payload: BillingOwnerCSPPayload
    ) -> BillingOwnerCSPResult:
        return BillingOwnerCSPResult(billing_owner_id="ea-mock-billing-owner-id")
