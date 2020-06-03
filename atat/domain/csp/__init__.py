import os

from .cloud import MockCloudProvider, HybridCloudProvider, AzureCloudProvider
from .files import AzureFileService, MockFileService
from .reports import MockReportingProvider


class CSP:
    def __init__(self, csp, config, **kwargs):
        azure = AzureCloudProvider(config)
        mock = MockCloudProvider(config, **kwargs)
        hybrid = HybridCloudProvider(azure, mock, config)

        if csp == "azure":
            self.cloud = azure
            self.files = AzureFileService(config)
        elif csp in ("mock-test", "mock"):
            self.cloud = mock
            self.files = MockFileService(config)
        elif csp == "hybrid":
            self.cloud = hybrid
            self.files = AzureFileService(config)
        else:
            raise Exception(f"Unexpected CSP value provided: {csp}")

        self.reports = MockReportingProvider()


def make_csp_provider(app, csp=None):
    simulate_failures = app.config.get("SIMULATE_API_FAILURE")
    app.logger.info(f"Created a cloud service provider in '{csp}' mode!")
    app.csp = CSP(
        csp,
        app.config,
        with_delay=simulate_failures,
        with_failure=simulate_failures,
        with_authorization=simulate_failures,
    )
