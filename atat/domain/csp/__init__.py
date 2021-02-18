import os

from .cloud import AzureCloudProvider, HybridCloudProvider, MockCloudProvider
from .files import AzureFileService, MockFileService
from .reports import MockReportingProvider


class CSP:
    def __init__(self, csp, config, **kwargs):
        if csp == "azure":
            self.cloud = AzureCloudProvider(config)
            self.files = AzureFileService(config)
        elif csp in ("mock-test", "mock"):
            self.cloud = MockCloudProvider(config, **kwargs)
            self.files = MockFileService(config)
        elif csp == "hybrid":
            azure = AzureCloudProvider(config)
            mock = MockCloudProvider(config, **kwargs)
            self.cloud = HybridCloudProvider(azure, mock, config)
            self.files = AzureFileService(config)
        else:
            raise ValueError(f"Unexpected CSP value provided: {csp}")

        self.reports = MockReportingProvider()


def make_csp_provider(app, csp=None):
    simulate_failures = app.config.get("SIMULATE_API_FAILURE", False)
    app.logger.info("Created a cloud service provider in '%s' mode!", csp)
    app.csp = CSP(
        csp,
        app.config,
        with_delay=simulate_failures,
        with_failure=simulate_failures,
        with_authorization=simulate_failures,
    )
