#!/usr/bin/env python
# Add root application dir to the python path
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

import argparse
import random
from secrets import token_urlsafe
import string

import factory
import yaml

from atat.domain.csp.cloud.utils import (
    get_principal_auth_token,
    create_active_directory_user,
)
from atat.domain.csp.cloud.models import ServicePrincipalTokenPayload, UserCSPPayload

GRAPH_RESOURCE = "https://graph.microsoft.com"
TOKEN_SCOPE = GRAPH_RESOURCE + "/.default"


def get_token(scope, client_id, client_secret, tenant_id):
    payload = ServicePrincipalTokenPayload(
        scope=scope, client_id=client_id, client_secret=client_secret,
    )
    return get_principal_auth_token(tenant_id, payload)


def create_user(token, tenant_id, tenant_host_name):
    first_name = factory.Faker("first_name").generate()
    last_name = factory.Faker("last_name").generate()
    email = f"{first_name}.{last_name}@example.com".lower()
    password = token_urlsafe(32)
    payload = UserCSPPayload(
        tenant_id=tenant_id,
        display_name=f"{first_name} {last_name}",
        tenant_host_name=tenant_host_name,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    response = create_active_directory_user(
        token, GRAPH_RESOURCE, payload, password_reset=False
    )
    response.raise_for_status()
    result = payload.dict()
    result.update(
        {
            "first_name": first_name,
            "last_name": last_name,
            "login_name": payload.user_principal_name,
            "dod_id": "".join(random.choices(string.digits, k=10)),
        }
    )
    return result


def run(cli_args):
    users = []
    token = get_token(
        TOKEN_SCOPE, cli_args.client_id, cli_args.client_secret, cli_args.tenant_id
    )
    for _ in range(cli_args.user_count):
        user = create_user(token, cli_args.tenant_id, cli_args.tenant_name)
        users.append(user)

    with open(cli_args.out, "w") as output:
        yaml.dump(users, output)


def parser():
    parser = argparse.ArgumentParser(
        description="""
This script will add a specified number of random sample users to an Azure
Active Directory tenant.

It requires a service principal with a minimum of User.ReadWrite.All Graph API
permissions to the AAD tenant:
https://docs.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0&tabs=http

The YAML output includes the details created for each user as well as a fake
DoD ID/EDIPI in case the information needs to be loaded into the database
separately.
"""
    )
    parser.add_argument("tenant_id", type=str, help="GUID of the AAD tenant")
    parser.add_argument(
        "client_id", type=str, help="Application (client) GUID of the App Registration"
    )
    parser.add_argument(
        "client_secret", type=str, help="Client secret for the App Registration"
    )
    parser.add_argument(
        "tenant_name",
        type=str,
        help="The subdomain of the tenant hostname, i.e., 'contoso' if the tenant hostname is 'contoso.onmicrosoft.com'",
    )
    parser.add_argument("user_count", type=int, help="The number of users to create")
    parser.add_argument(
        "-o",
        "--out",
        default="users.yml",
        type=str,
        help="The location of the YAML output file",
    )
    return parser


if __name__ == "__main__":
    cli_args = parser().parse_args()
    run(cli_args)
