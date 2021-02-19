#! /usr/bin/python

import base64
import click
import datetime
from os import path
import requests
import time
import uuid

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    serialize_key_and_certificates,
)
from cryptography.x509.oid import NameOID
from typing import NoReturn


def authenticate(tenant_id: str, application_id: str, password: str):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": application_id,
        "client_secret": password,
        "scope": "https://graph.microsoft.com/.default",
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def create_templated_app_registration(access_token: str):
    # application template id is prescribed for SSO SAML providers
    # https://docs.microsoft.com/en-us/graph/application-saml-sso-configure-api?tabs=http#create-the-gallery-application
    url = "https://graph.microsoft.com/beta/applicationTemplates/8adf8e6e-67b2-4cf2-a259-e3dc5476c621/instantiate"
    data = {"displayName": "ATAT SAML Auth"}

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    response_json = response.json()
    sp_object_id = response_json["servicePrincipal"]["objectId"]
    application_object_id = response_json["application"]["objectId"]

    print(f"Created application ({application_object_id})")

    return (sp_object_id, application_object_id)


def wait_for_sp_creation(sp_object_id: str, access_token: str):
    attempts = 0
    while attempts < 10:
        attempts = attempts + 1
        print(f"Polling for {sp_object_id}...")
        headers = {"Authorization": f"Bearer {access_token}"}
        poll_response = requests.get(
            f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_object_id}",
            headers=headers,
        )

        if poll_response.ok:
            break
        elif poll_response.status_code == 404:
            wait_time = 1 + attempts
            print(f"Not found, checking again in {wait_time} seconds")
            time.sleep(wait_time)
        else:
            raise Exception(
                f"Received an unexpected status of {poll_response.status_code}"
            )

    else:
        raise Exception(
            f"Failed to find service principle {sp_object_id} after {attempts} attempts"
        )


def enable_saml(sp_object_id: str, access_token: str):
    url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_object_id}"
    data = {"preferredSingleSignOnMode": "saml"}

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    requests.patch(url, json=data, headers=headers).raise_for_status()


def register_urls_with_application(
    application_object_id: str, hostname: str, access_token: str
):
    url = f"https://graph.microsoft.com/v1.0/applications/{application_object_id}"
    data = {
        "web": {
            "redirectUris": [f"https://{hostname}/login?acs"],
            "logoutUrl": f"https://{hostname}/login?sls",
        },
        "identifierUris": [f"https://{hostname}"],
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.patch(url, json=data, headers=headers)
    response.raise_for_status()


def register_urls_with_service_principle(
    sp_object_id: str, hostname: str, access_token: str
):
    url = f"https://graph.microsoft.com/beta/servicePrincipals/{sp_object_id}"
    data = {"loginUrl": f"https://{hostname}/login"}
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.patch(url, json=data, headers=headers)
    response.raise_for_status()


def register_self_signed_certificate(sp_object_id: str, access_token: str):
    """This function generates a self-signed certificate and registers it with the given
    service principle. The process and output are adapted from the official azure
    documentation:
    https://docs.microsoft.com/en-us/graph/application-saml-sso-configure-api?tabs=http#step-4-configure-signing-certificate

    https://cryptography.io/en/latest/x509/tutorial.html#creating-a-self-signed-certificate
    """
    # Generate uuid to use as a password
    saml_signing_password = str(uuid.uuid4())

    # Generate self signed certificate.
    key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    # Various details about who we are. For a self-signed certificate the
    # subject and issuer are always the same.
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Pennsylvania"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Philadelphia"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PromptWorks"),
            x509.NameAttribute(NameOID.COMMON_NAME, "PromptWorks"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(
            # Our certificate will be valid for 1 year
            datetime.datetime.utcnow()
            + datetime.timedelta(days=365)
        )
        .add_extension(
            # since this cert is used to sign SAML transactions, doesn't matter what the DNS name is
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256(), backend=default_backend())
    )

    pem_pkcs12 = serialize_key_and_certificates(
        b"saml_cert",
        key,
        cert,
        None,
        BestAvailableEncryption(saml_signing_password.encode()),
    )

    url = f"https://graph.microsoft.com/beta/servicePrincipals/{sp_object_id}"

    sign_and_password_guid = str(uuid.uuid4())
    verify_guid = str(uuid.uuid4())

    private_key = base64.encodebytes(pem_pkcs12).decode().strip("\n")
    public_key = (
        base64.encodebytes(cert.public_bytes(Encoding.PEM)).decode().strip("\n")
    )
    thumbprint = (
        base64.encodebytes(cert.fingerprint(hashes.SHA256())).decode().strip("\n")
    )

    data = {
        "keyCredentials": [
            {
                "customKeyIdentifier": thumbprint,
                "endDateTime": cert.not_valid_after.isoformat(),
                "keyId": sign_and_password_guid,
                "startDateTime": cert.not_valid_before.isoformat(),
                "type": "X509CertAndPassword",
                "usage": "Sign",
                "key": private_key,
                "displayName": "CN=ATAT SAML Signing Certificate",
            },
            {
                "customKeyIdentifier": thumbprint,
                "endDateTime": cert.not_valid_after.isoformat(),
                "keyId": verify_guid,
                "startDateTime": cert.not_valid_before.isoformat(),
                "type": "AsymmetricX509Cert",
                "usage": "Verify",
                "key": public_key,
                "displayName": "CN=ATAT SAML Verification Certificate",
            },
        ],
        "passwordCredentials": [
            {
                "customKeyIdentifier": thumbprint,
                "keyId": sign_and_password_guid,
                "endDateTime": cert.not_valid_after.isoformat(),
                "startDateTime": cert.not_valid_before.isoformat(),
                "secretText": saml_signing_password,
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.patch(url, json=data, headers=headers)
    response.raise_for_status()


def assign_user_to_saml_idp(user_object_id: str, sp_object_id: str, access_token: str):
    url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_object_id}/appRoleAssignments"
    data = {
        "principalId": user_object_id,
        "principalType": "User",
        "resourceId": sp_object_id,
        "appRoleId": "18d14569-c3bd-439b-9a66-3a2aee01d14f",
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code != 201:
        print(f"Failed to assign user {user_object_id}")
        print(response.json())


@click.command()
@click.argument("tenant-id",)
@click.argument("application-id")
@click.argument("password")
@click.argument("hostname")
def main(tenant_id: str, application_id: str, password: str, hostname: str) -> NoReturn:
    if not path.exists("user_service_principals.txt.txt"):
        print("Could not locate user_service_principals.txt")
        print(
            "This file must exist and contain one user object id per line, each to be registered with the identity provider."
        )
        exit(1)

    access_token = authenticate(tenant_id, application_id, password)

    # Initialize templated app and service principle
    sp_object_id, application_object_id = create_templated_app_registration(
        access_token
    )
    wait_for_sp_creation(sp_object_id, access_token)

    # Configure SAML SSO
    enable_saml(sp_object_id, access_token)
    register_urls_with_application(application_object_id, hostname, access_token)
    register_urls_with_service_principle(sp_object_id, hostname, access_token)
    register_self_signed_certificate(sp_object_id, access_token)

    # Register users
    with open("user_service_principals.txt", "r") as user_service_principals:
        for line in user_service_principals.readlines():
            user_object_id = line.strip()
            assign_user_to_saml_idp(user_object_id, sp_object_id, access_token)


if __name__ == "__main__":
    main()
