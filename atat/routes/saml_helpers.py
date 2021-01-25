import random
import re
import string
from urllib.parse import urlparse

import cachetools.func
from flask import current_app as app
from flask import g, session
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.errors import OneLogin_Saml2_ValidationError
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser

from atat.domain.exceptions import NotFoundError, UnauthenticatedError
from atat.domain.users import Users
from atat.routes.routes_helpers import match_url_pattern

SAM_ACCOUNT_FORMAT = re.compile("(1\d{9})\.(MIL|CIV|CTR)")

DESIGNATIONS = {
    "MIL": "military",
    "CIV": "civilian",
    "CTR": "contractor",
}

AGENCY_CODES = {
    "F": "air_force",
    "N": "navy",
    "M": "marine_corps",
    "A": "army",
}

# The SAML attributes happen to have names in a URL format
# This does not mean that there is communication via HTTP
class EIFSAttributes:
    GIVEN_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
    LAST_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
    EMAIL = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
    # SAM Account Name provides both DoD ID and Short Designation (military/civlian/contractor)
    # Name is provided in format 1234567890.MIL
    SAM_ACCOUNT_NAME = "samAccountName"
    US_CITIZEN = "extensionAttribute4"
    AGENCY_CODE = "extensionAttribute1"
    MOBILE = "mobile"
    TELEPHONE = "telephoneNumber"


class AzureAttributes:
    GIVEN_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
    LAST_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"


def prepare_idp_url(request):
    saml_auth = init_saml_auth(request)
    return _prepare_login_url(saml_auth, request)


def prepare_idp_dev_url(request):
    saml_auth = init_saml_auth_dev(request)
    return _prepare_login_url(saml_auth, request)


def _prepare_login_url(saml_auth, request):
    sso_built_url = saml_auth.login()
    request_id = saml_auth.get_last_request_id()
    session["AuthNRequestID"] = request_id

    _cache_params_in_session(request)

    return sso_built_url


def _cache_params_in_session(request):
    query_string_parameters = {}

    next_param = match_url_pattern(request.args.get("next"))
    if next_param:
        query_string_parameters["next_param"] = next_param

    username_param = request.args.get("username")
    if username_param:
        query_string_parameters["username_param"] = username_param

    dod_id_param = request.args.get("dod_id")
    if dod_id_param:
        query_string_parameters["dod_id_param"] = dod_id_param

    session.pop("query_string_parameters", None)
    if query_string_parameters:
        session["query_string_parameters"] = query_string_parameters


def load_attributes_from_assertion(request):
    saml_auth = init_saml_auth(request)
    return _process_assertion_into_attributes(saml_auth)


def load_attributes_from_dev_assertion(request):
    saml_auth = init_saml_auth_dev(request)
    return _process_assertion_into_attributes(saml_auth)


def _process_assertion_into_attributes(saml_auth):
    _validate_saml_assertion(saml_auth)
    # parsed attribute values are returned in array by default,
    # but we only expect a single value for each attribute
    saml_attributes = {k: v[0] for k, v in saml_auth.get_attributes().items()}
    return saml_attributes


def _validate_saml_assertion(saml_auth):
    request_id = session.get("AuthNRequestID")

    try:
        saml_auth.process_response(request_id=request_id)
        app.logger.info("writing response %s", request_id)
    except OneLogin_Saml2_ValidationError as error_message:
        app.logger.error("OneLogin_Saml2_ValidationError detected: %s", error_message)
        raise UnauthenticatedError("SAML Validation Failed")

    errors = saml_auth.get_errors()
    if len(errors) == 0:
        session.pop("AuthNRequestID", None)
    else:
        app.logger.error(
            "SAML response from IdP contained the following errors: %s",
            ", ".join(errors),
        )
        app.logger.error(saml_auth.get_last_error_reason())
        raise UnauthenticatedError("SAML Authentication Failed")


def unique_dod_id():
    """
    Generate a new DOD ID for a development user.
    """
    # Ensure that the identifier always starts with a leading 0
    new_dod_id = "".join(random.choices(string.digits, k=9)).zfill(10)  # nosec
    try:
        Users.get_by_dod_id(new_dod_id)
    except NotFoundError:
        return new_dod_id
    return unique_dod_id()


def init_saml_auth(request, saml_config=None):
    if not saml_config:
        saml_config = _make_saml_config()
    saml_request_config = _prepare_flask_request(request)
    auth = OneLogin_Saml2_Auth(saml_request_config, saml_config)
    saml_settings = auth.get_settings()
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    if len(errors) != 0:
        app.logger.error("Error found on Metadata: %s", ", ".join(errors))
        raise UnauthenticatedError("SAML Metadata Validation Failed")
    else:
        return auth


def init_saml_auth_dev(request):
    saml_dev_config = _make_dev_saml_config()
    return init_saml_auth(request, saml_config=saml_dev_config)


def get_user_from_saml_attributes(saml_attributes):
    """Finds a user based on DoD ID in SAML attributes or creates a new user
    with the info if one isn't found.
    """
    try:
        sam_account_name = saml_attributes.get(EIFSAttributes.SAM_ACCOUNT_NAME)
        dod_id, short_designation = SAM_ACCOUNT_FORMAT.match(sam_account_name).groups()
        return Users.get_by_dod_id(dod_id)
    except TypeError:
        app.logger.error("SAML response missing SAM Account Name")
        raise Exception("SAML response missing SAM Account Name")
    except AttributeError:
        app.logger.error("Incorrect format of SAM Account Name %s", sam_account_name)
        raise Exception("SAM Account Name Incorrectly Formatted")
    except NotFoundError:
        app.logger.info("No user found for DoD ID %s, creating...", dod_id)

    saml_user_details = {}
    saml_user_details["first_name"] = saml_attributes.get(EIFSAttributes.GIVEN_NAME)
    saml_user_details["last_name"] = saml_attributes.get(EIFSAttributes.LAST_NAME)
    saml_user_details["email"] = saml_attributes.get(EIFSAttributes.EMAIL)

    saml_user_details["designation"] = DESIGNATIONS.get(short_designation)

    is_us_citizen = saml_attributes.get(EIFSAttributes.US_CITIZEN)
    if is_us_citizen == "Y":
        saml_user_details["citizenship"] = "United States"

    agency_code = saml_attributes.get(EIFSAttributes.AGENCY_CODE)
    saml_user_details["service_branch"] = AGENCY_CODES.get(agency_code)

    telephoneNumber = saml_attributes.get(EIFSAttributes.TELEPHONE)
    mobile = saml_attributes.get(EIFSAttributes.MOBILE)

    saml_user_details["phone_number"] = telephoneNumber or mobile

    return Users.get_or_create_by_dod_id(dod_id, **saml_user_details)


def _prepare_flask_request(request):
    """
    Prepares a request object for use in building the SAML request.
    Since we use an AD FS SAML Identity Provider, we need to ensure
    that lowercase_urlencoding is enabled, per https://github.com/onelogin/python-saml/pull/144
    """
    url_data = urlparse(request.url)
    return {
        "https": "on" if request.scheme == "https" else "off",
        "http_host": request.host,
        "server_port": url_data.port,
        "script_name": request.path,
        "get_data": request.args.copy(),
        "lowercase_urlencoding": True,  # Required by ADFS
        "post_data": request.form.copy(),
    }


def _make_dev_saml_config():
    config = {
        "strict": True,
        "debug": True,
        "sp": {
            "entityId": app.config["SAML_DEV_ENTITY_ID"],
            "assertionConsumerService": {
                "url": app.config["SAML_DEV_ACS"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": app.config["SAML_DEV_SLS"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
    }

    config["idp"] = _get_idp_config(app.config["SAML_DEV_IDP_URI"], validate_cert=False)

    return config


def _make_saml_config():
    config = {
        "strict": True,
        "debug": g.dev,
        "sp": {
            "entityId": app.config["SAML_ENTITY_ID"],
            "assertionConsumerService": {
                "url": app.config["SAML_ACS"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": app.config["SAML_SLS"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
        },
        "security": {
            "wantAssertionsSigned": True,  # Needed by EIFS
            "requestedAuthnContext": False,  # Needed by EIFS
            "wantNameId": False,  # EIFS sometimes lacks NameID as a result of missing email addresses
        },
    }

    config["idp"] = _get_idp_config(app.config["SAML_IDP_URI"], validate_cert=False)

    return config


@cachetools.func.ttl_cache(maxsize=2, ttl=3600)
def _get_idp_config(idp_uri, validate_cert=True):
    retries = 0
    while retries < 3:
        try:
            remote_config = OneLogin_Saml2_IdPMetadataParser.parse_remote(
                idp_uri, validate_cert=validate_cert
            )
            return remote_config["idp"]
        except Exception as e:
            app.logger.warning("Failed to load %s: %s", idp_uri, e)
            retries = retries + 1

    app.logger.error("Unable to load SAML Metadata from %s", idp_uri)
    raise Exception("Failed to load SAML Metadata")


def get_or_create_dev_saml_user(saml_attributes):
    saml_user_details = {}
    saml_user_details["first_name"] = saml_attributes.get(AzureAttributes.GIVEN_NAME)
    saml_user_details["last_name"] = saml_attributes.get(AzureAttributes.LAST_NAME)
    try:
        # We check for an existing user by searching for any user with the
        # same first and last name. This could possibly cause collisions
        # of two users with the exact same first and last name.
        # However, the Azure SAML token doesn't seem to currently provide
        # more distinquishing detail than that that
        user = Users.get_by_first_and_last_name(
            saml_user_details["first_name"], saml_user_details["last_name"]
        )
    except NotFoundError:
        new_dod_id = unique_dod_id()
        created_user = Users.create(new_dod_id, **saml_user_details)
        user = created_user

    return user
