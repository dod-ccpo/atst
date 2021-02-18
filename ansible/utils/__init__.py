from ansible.utils.display import Display
from ansible.errors import AnsibleError
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from msrest.exceptions import AuthenticationError, ClientRequestError
import requests

_FAILED_TO_FETCH_SECRET = "Failed to fetch secret"


def acquire_token():
    _display = Display()
    token_params = {"api-version": "2018-02-01", "resource": "https://vault.azure.net"}
    token_headers = {"Metadata": "true"}
    token = None
    try:
        token_res = requests.get(
            "https://169.254.169.254/metadata/identity/oauth2/token",
            params=token_params,
            headers=token_headers,
            timeout=10,
        )
        token = token_res.json().get("access_token")
        if token is None:
            _display.v(
                "Successfully called MSI endpoint, but no token was available. Will use service principal if provided."
            )
    except requests.exceptions.RequestException:
        _display.v("Unable to fetch MSI token. Will use service principal if provided.")

    return token


def get_azure_credentials(tenant_id=None, client_id=None, secret=None):
    # TODO: should try InteractiveBrowserCredential if kwargs are None
    if tenant_id:
        return ClientSecretCredential(tenant_id, client_id, secret)


def get_secret_client(vault_url, kwargs):
    client_id = kwargs.pop("client_id", None)
    secret = kwargs.pop("secret", None)
    tenant_id = kwargs.pop("tenant_id", None)

    try:
        credentials = get_azure_credentials(
            tenant_id=tenant_id, client_id=client_id, secret=secret
        )
        return SecretClient(vault_url, credential=credentials)
    except AuthenticationError:
        raise AnsibleError("Invalid credentials provided.")


def lookup_secret_non_msi(terms, vault_url, kwargs):
    import logging

    logging.getLogger("msrestazure.azure_active_directory").addHandler(
        logging.NullHandler()
    )
    logging.getLogger("msrest.service_client").addHandler(logging.NullHandler())

    client = get_secret_client(vault_url, kwargs)
    ret = []
    for term in terms:
        try:
            secret_val = client.get_secret(term).value
            ret.append(secret_val)
        except ClientRequestError:
            raise AnsibleError("Error occurred in request")
        except ResourceNotFoundError:
            raise AnsibleError(f"{_FAILED_TO_FETCH_SECRET} {term}.")
    return ret


def lookup_secret_msi(token, terms, vault_url):
    ret = []
    secret_params = {"api-version": "2016-10-01"}
    secret_headers = {"Authorization": "Bearer " + token}
    for term in terms:
        try:
            secret_res = requests.get(
                vault_url + "/secrets/" + term,
                params=secret_params,
                headers=secret_headers,
            )
            ret.append(secret_res.json()["value"])
        except requests.exceptions.RequestException:
            raise AnsibleError(f"{_FAILED_TO_FETCH_SECRET}: {term} via MSI endpoint")
        except KeyError:
            raise AnsibleError(f"{_FAILED_TO_FETCH_SECRET} {term}.")
    return ret


def lookup_secret_list_non_msi(terms, vault_url, kwargs):
    import logging

    logging.getLogger("msrestazure.azure_active_directory").addHandler(
        logging.NullHandler()
    )
    logging.getLogger("msrest.service_client").addHandler(logging.NullHandler())

    client = get_secret_client(vault_url, kwargs)
    ret = []
    for term in terms:
        try:
            secret_val = client.list_properties_of_secrets()
            for secret_property in secret_val:
                ret.append(secret_property.name)
        except ClientRequestError:
            raise AnsibleError("Error occurred in request")
        except ResourceNotFoundError:
            raise AnsibleError(f"{_FAILED_TO_FETCH_SECRET} {term}.")
    return ret
