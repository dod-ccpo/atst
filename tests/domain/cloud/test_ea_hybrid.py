import pytest

from atat.domain.csp import CSP


@pytest.fixture(scope="session")
def ea_hybrid_csp(app):
    return CSP(
        "ea-hybrid",
        app.config,
        with_delay=False,
        with_failure=False,
        with_authorization=False,
    )


def test_ea_create_billing_owner(ea_hybrid_csp):
    billing_owner = ea_hybrid_csp.create_billing_owner()
    assert billing_owner.billing_owner_id == "ea-mock-billing-owner-id"


def test_get_reporting_data(ea_hybrid_csp):
    mock_reporting_data = ea_hybrid_csp.get_reporting_data()
    assert mock_reporting_data.columns is not None
