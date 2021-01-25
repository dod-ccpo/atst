import re
from unittest.mock import Mock, patch

import pytest
from flask import session
from onelogin.saml2.errors import OneLogin_Saml2_ValidationError

from atat.domain.exceptions import UnauthenticatedError
from atat.routes import get_user_from_saml_attributes
from atat.routes.saml_helpers import (
    EIFSAttributes,
    _cache_params_in_session,
    _get_idp_config,
    _prepare_login_url,
    _validate_saml_assertion,
    init_saml_auth,
    init_saml_auth_dev,
    unique_dod_id,
)
from tests.factories import UserFactory


def test_prepare_login_url_success():
    request = Mock(args={})
    saml_auth = Mock(
        login=lambda: "https://idp.saml", get_last_request_id=lambda: "ABC123"
    )

    login_url = _prepare_login_url(saml_auth, request)

    assert login_url == "https://idp.saml"
    assert session["AuthNRequestID"] == "ABC123"


def test_qp_cache_success():
    request = Mock(
        args={"next": "/home", "username": "Amanda", "dod_id": "1234567890",}
    )

    _cache_params_in_session(request)

    qsp = session["query_string_parameters"]

    assert qsp["next_param"] == "/home"
    assert qsp["username_param"] == "Amanda"
    assert qsp["dod_id_param"] == "1234567890"


def test_qp_cache_cleared():
    request = Mock(args={})

    session["query_string_parameters"] = {"next_param": "https://gone.com"}
    _cache_params_in_session(request)

    assert "query_string_parameters" not in session


def test_validate_saml_assertion_success():
    saml_auth = Mock(process_response=Mock(), get_errors=Mock(return_value=[]))

    session["AuthNRequestID"] = "ABC123"
    _validate_saml_assertion(saml_auth)

    assert "AuthNRequestID" not in session


def test_validate_saml_assertion_invalid_response():
    saml_auth = Mock(
        process_response=Mock(side_effect=[OneLogin_Saml2_ValidationError("Invalid")])
    )

    with pytest.raises(UnauthenticatedError):
        _validate_saml_assertion(saml_auth)


def test_validate_saml_assertion_valid_with_errors(mock_logger):
    mock_last_err = Mock(return_value="Error")
    saml_auth = Mock(
        process_response=Mock(),
        get_errors=Mock(return_value=["Error"]),
        get_last_error_reason=mock_last_err,
    )

    session["AuthNRequestID"] = "ABC123"
    with pytest.raises(UnauthenticatedError):
        _validate_saml_assertion(saml_auth)

    assert session["AuthNRequestID"] == "ABC123"
    mock_last_err.assert_called()


def test_unique_dod_id_10_digits():
    dod_id_regex = re.compile(r"\d{10}")
    assert dod_id_regex.match(unique_dod_id())


def create_saml_auth_mock(validation_result=None):
    if validation_result is None:
        validation_result = []

    return Mock(
        **{
            "get_settings.return_value.get_sp_metadata.return_value": Mock(),
            "get_settings.return_value.validate_metadata.return_value": validation_result,
        }
    )


@patch("atat.routes.saml_helpers.OneLogin_Saml2_Auth")
@patch("atat.routes.saml_helpers._prepare_flask_request")
@patch("atat.routes.saml_helpers._make_saml_config")
def test_saml_init_success(mock_make_config, mock_prepare_request, mock_saml_auth):
    request = Mock()
    mock_auth = create_saml_auth_mock()
    mock_saml_auth.return_value = mock_auth
    assert init_saml_auth(request) == mock_auth


@patch("atat.routes.saml_helpers.OneLogin_Saml2_Auth")
@patch("atat.routes.saml_helpers._prepare_flask_request")
@patch("atat.routes.saml_helpers._make_saml_config")
def test_saml_init_errors(mock_make_config, mock_prepare_request, mock_saml_auth):
    request = Mock()
    mock_saml_auth.return_value = create_saml_auth_mock(
        validation_result=["Invalid Configuration"]
    )
    with pytest.raises(UnauthenticatedError):
        init_saml_auth(request)


@patch("atat.routes.saml_helpers.OneLogin_Saml2_Auth")
@patch("atat.routes.saml_helpers._prepare_flask_request")
@patch("atat.routes.saml_helpers._make_dev_saml_config")
def test_dev_saml_init_success(mock_make_config, mock_prepare_request, mock_saml_auth):
    request = Mock()
    mock_auth = create_saml_auth_mock()
    mock_saml_auth.return_value = mock_auth
    assert init_saml_auth_dev(request) == mock_auth


@patch("atat.routes.saml_helpers.OneLogin_Saml2_Auth")
@patch("atat.routes.saml_helpers._prepare_flask_request")
@patch("atat.routes.saml_helpers._make_dev_saml_config")
def test_dev_saml_init_errors(mock_make_config, mock_prepare_request, mock_saml_auth):
    request = Mock()
    mock_saml_auth.return_value = create_saml_auth_mock(
        validation_result=["Invalid Configuration"]
    )
    with pytest.raises(UnauthenticatedError):
        init_saml_auth_dev(request)


@patch("atat.routes.saml_helpers.OneLogin_Saml2_IdPMetadataParser")
class TestGetIdPConfig:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _get_idp_config.cache_clear()

    def test_get_idp_config_success(self, mock_parser):
        idp_uri = "http://myidp.com/federationmetadata.xml"

        mock_parser.parse_remote = Mock(return_value={"idp": "config"})

        assert _get_idp_config(idp_uri) == "config"

    def test_get_idp_config_retries(self, mock_parser):
        idp_uri = "http://myidp.com/federationmetadata.xml"

        mock_parser.parse_remote = Mock(
            side_effect=[Exception("Connection Failed"), {"idp": "config"}]
        )

        assert _get_idp_config(idp_uri) == "config"
        assert mock_parser.parse_remote.call_count == 2

    def test_get_idp_config_retries_exceeded(self, mock_parser):
        idp_uri = "http://myidp.com/federationmetadata.xml"

        mock_parser.parse_remote = Mock(
            side_effect=[
                Exception("Connection Failed"),
                Exception("Connection Failed"),
                Exception("Connection Failed"),
            ]
        )

        with pytest.raises(Exception):
            _get_idp_config(idp_uri)

        assert mock_parser.parse_remote.call_count == 3

    def test_get_idp_config_success_cache(self, mock_parser):
        idp_uri = "http://myidp.com/federationmetadata.xml"

        mock_parser.parse_remote = Mock(return_value={"idp": "config"})

        assert _get_idp_config(idp_uri) == "config"
        _get_idp_config(idp_uri)

        assert mock_parser.parse_remote.call_count == 1


class TestSamlAttributes:
    @pytest.fixture(scope="function")
    def mock_attributes(self):
        return {
            EIFSAttributes.GIVEN_NAME: "",
            EIFSAttributes.LAST_NAME: "",
            EIFSAttributes.EMAIL: "",
            EIFSAttributes.SAM_ACCOUNT_NAME: "",
            EIFSAttributes.US_CITIZEN: "",
            EIFSAttributes.AGENCY_CODE: "",
            EIFSAttributes.MOBILE: "",
        }

    def test_get_user_from_saml_attributes(self, mock_attributes):
        expected_dod_id = "1234567890"
        saml_attributes = {
            **mock_attributes,
            **{
                EIFSAttributes.SAM_ACCOUNT_NAME: f"{expected_dod_id}.MIL",
                EIFSAttributes.US_CITIZEN: "Y",
                EIFSAttributes.AGENCY_CODE: "F",
            },
        }
        user = get_user_from_saml_attributes(saml_attributes)
        assert user.dod_id == expected_dod_id
        assert user.designation == "military"
        assert user.citizenship == "United States"
        assert user.service_branch == "air_force"

    def test_get_user_from_saml_attributes_missing_dod_id(self, mock_attributes):
        with pytest.raises(Exception):
            get_user_from_saml_attributes(mock_attributes)

    def test_get_user_from_saml_invalid_sam_format(self, mock_attributes):
        saml_attributes = {
            **mock_attributes,
            **{EIFSAttributes.SAM_ACCOUNT_NAME: "sam account name format changed",},
        }
        with pytest.raises(Exception):
            get_user_from_saml_attributes(saml_attributes)

    def test_get_user_from_saml_existing_user(self, mock_attributes):
        expected_dod_id = "1234567890"
        saml_attributes = {
            **mock_attributes,
            **{EIFSAttributes.SAM_ACCOUNT_NAME: f"{expected_dod_id}.MIL",},
        }
        expected_user = UserFactory.create(dod_id=expected_dod_id)

        assert expected_user == get_user_from_saml_attributes(saml_attributes)

    def test_get_user_from_saml_telephone_over_mobile(self, mock_attributes):
        expected_dod_id = "1234567890"
        saml_attributes = {
            **mock_attributes,
            **{
                EIFSAttributes.SAM_ACCOUNT_NAME: f"{expected_dod_id}.MIL",
                EIFSAttributes.MOBILE: "1234",
                EIFSAttributes.TELEPHONE: "5678",
            },
        }

        user = get_user_from_saml_attributes(saml_attributes)

        assert user.phone_number == "5678"

    def test_get_user_from_saml_mobile_fallback(self, mock_attributes):
        expected_dod_id = "1234567890"
        saml_attributes = {
            **mock_attributes,
            **{
                EIFSAttributes.SAM_ACCOUNT_NAME: f"{expected_dod_id}.MIL",
                EIFSAttributes.MOBILE: "1234",
            },
        }

        user = get_user_from_saml_attributes(saml_attributes)

        assert user.phone_number == "1234"
