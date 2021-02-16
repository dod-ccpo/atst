import json
import os
import subprocess
import logging
from os import path
from subprocess import CalledProcessError
from typing import Optional, Dict, NoReturn

import click
from click.utils import echo
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)
_TMP_PEM = "/tmp/dhparams.pem"


@click.command()
@click.option(
    "--sp_client_id",
    help="Client ID (Also called AppId) of the service principle created in phase1 - envvar: SP_CLIENT_ID",
    prompt="Service Principle used to provision infrastructure",
    envvar="SP_CLIENT_ID",
)
@click.option(
    "--sp_client_secret",
    help="Service Principle's password - envvar: SP_CLIENT_SECRET",
    prompt="Service Principle's password",
    envvar="SP_CLIENT_SECRET",
)
@click.option(
    "--subscription_id",
    help="The SubscriptionId (See subscriptions in Azure portal) that will house these resources - envvar: SUBSCRIPTION_ID",
    prompt="Subscription ID",
    envvar="SUBSCRIPTION_ID",
)
@click.option("--tenant_id", help="tenant id - envvar: TENANT_ID", envvar="TENANT_ID")
@click.option(
    "--ops_resource_group",
    help="Resource group created to hold all the resources for operations only - envvar: OPS_RESOURCE_GROUP",
    prompt="Name of operations resource group",
    envvar="OPS_RESOURCE_GROUP",
)
@click.option(
    "--ops_storage_account",
    help="Name of Storage Account that holds the terraform state and inputs for this process - envvar: OPS_STORAGE_ACCOUNT",
    prompt="Name of Ops Storage Account",
    envvar="OPS_STORAGE_ACCOUNT",
)
@click.option(
    "--namespace",
    help="Namespacing of your environment - envvar: NAMESPACE",
    envvar="NAMESPACE",
)
@click.option(
    "--ops_tf_application_container",
    default="tf-application",
    help="Name of the container (folder) in the ops_storage_account that holds the terraform state from application - envvar: OPS_TF_APPLICATION_CONTAINER",
    envvar="OPS_TF_APPLICATION_CONTAINER",
)
@click.option(
    "--ops_config_container",
    default="config",
    help="Name of the container (folder) in the ops_storage_account that holds the config that will be needed by the application - envvar: OPS_CONFIG_CONTAINER",
    envvar="OPS_CERTS_CONTAINER",
)
@click.option(
    "--ops_registry",
    help="Name of the registry that has the ops image - envvar: OPS_REGISTRY",
    envvar="OPS_REGISTRY",
)
@click.option(
    "--commit_sha",
    help="Name of the registry that has the ops image - envvar: COMMIT_SHA",
    envvar="COMMIT_SHA",
)
@click.option(
    "--logging_workspace",
    help="Name of the logging workspace - envvar: LOGGING_WORKSPACE",
    envvar="LOGGING_WORKSPACE",
)
def provision(
    sp_client_id,
    sp_client_secret,
    subscription_id,
    tenant_id,
    ops_resource_group,
    ops_storage_account,
    namespace,
    ops_tf_application_container,
    ops_config_container,
    ops_registry,
    commit_sha,
    logging_workspace,
):
    login(sp_client_id, sp_client_secret, subscription_id, tenant_id)

    try:
        download_file(
            ops_storage_account, ops_config_container, "dhparams.pem", _TMP_PEM,
        )
        ssl_process = None
    except FileNotFoundError:
        ssl_process = diffie_helman(encryption=4096)

    download_file(
        ops_storage_account, ops_config_container, "atatdev.pem", "/tmp/atatdev.pem"
    )

    download_file(
        ops_storage_account,
        ops_config_container,
        "app.tfvars.json",
        "/tmp/app.tfvars.json",
    )

    pause_until_complete(ssl_process)

    terraform_application(
        sp_client_id=sp_client_id,
        sp_client_secret=sp_client_secret,
        subscription_id=subscription_id,
        tenant_id=tenant_id,
        backend_resource_group_name=ops_resource_group,
        backend_storage_account_name=ops_storage_account,
        backend_container_name=ops_tf_application_container,
        namespace=namespace,
    )


def login(sp_client_id, sp_client_secret, subscription_id, tenant_id):
    os.environ["ARM_CLIENT_ID"] = sp_client_id
    os.environ["ARM_CLIENT_SECRET"] = sp_client_secret
    os.environ["ARM_SUBSCRIPTION_ID"] = subscription_id
    os.environ["ARM_TENANT_ID"] = tenant_id
    subprocess.run(
        f"az login --service-principal --username {sp_client_id} --password {sp_client_secret} --tenant {tenant_id}".split()
    ).check_returncode()


def download_file(
    storage_account: str, container_name: str, file_name: str, dest_path: str
) -> int:

    result = subprocess.run(
        "az storage blob exists --account-name {storage_account} --container-name {container_name} --name {file_name} -o tsv".split(),
        capture_output=True,
    )
    if result.stdout == "False":
        echo(f"{file_name} not found")
        raise FileNotFoundError(file_name)

    result = subprocess.run(
        f"az storage blob download --account-name {storage_account} --container-name {container_name} --name {file_name} -f {dest_path} --no-progress".split(),
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        echo(result.stdout)
        echo(result.stderr)
        echo("Could not find the target file in the storage account.")
        echo(f"You need to upload {file_name} manually to the storage account.")
        raise FileNotFoundError(file_name)

    if not os.stat(dest_path).st_size:
        echo("Could not find the target file in the storage account.")
        echo(f"You need to upload {file_name} manually to the storage account.")
        raise FileNotFoundError(dest_path)

    return result.returncode


def terraform_application(
    sp_client_id,
    sp_client_secret,
    subscription_id,
    tenant_id,
    backend_resource_group_name,
    backend_storage_account_name,
    backend_container_name,
    namespace,
    backend_key="terraform.tfstate",
    bootrap_container_name="tf-bootstrap",
):

    logger.info("terraform_application")

    cwd = path.join("../", "../", "terraform", "providers", "application_env")

    default_args = {"cwd": cwd}

    backend_configs = [
        f"-backend-config=resource_group_name={backend_resource_group_name}",
        f"-backend-config=storage_account_name={backend_storage_account_name}",
        f"-backend-config=container_name={backend_container_name}",
        f"-backend-config=key={backend_key}",
    ]
    try:
        init_cmd = ["terraform", "init", *backend_configs, "."]
        print(init_cmd)
        subprocess.run(init_cmd, **default_args).check_returncode()

        tfvars = [
            f"-var=operator_subscription_id={subscription_id}",
            f"-var=operator_client_id={sp_client_id}",
            f"-var=operator_client_secret={sp_client_secret}",
            f"-var=operator_tenant_id={tenant_id}",
            f"-var=ops_resource_group={backend_resource_group_name}",
            f"-var=ops_storage_account={backend_storage_account_name}",
            f"-var=tf_bootstrap_container={bootrap_container_name}",
            f"-var=deployment_namespace={namespace}",
        ]
        cmd = [
            "terraform",
            "plan",
            "-input=false",
            "-out=plan.tfplan",
            "-var-file=/tmp/app.tfvars.json",
            "-no-color",
            *tfvars,
            ".",
        ]
        print(cmd)
        subprocess.run(cmd, **default_args).check_returncode()
        print("terraform apply plan.tfplan")
        subprocess.run(
            "terraform apply plan.tfplan".split(), **default_args
        ).check_returncode()

    except CalledProcessError as err:
        echo("=" * 50)
        echo(f"Failed running {err.cmd}")
        echo("=" * 50)
        echo(err.stdout)
        echo("=" * 50)
        echo(err.stderr)
        raise


def diffie_helman(encryption: int = 4096) -> Optional[subprocess.Popen]:
    logger.info("diffie_helman")
    if path.exists(_TMP_PEM):
        return
    return subprocess.Popen(
        ["openssl", "dhparam", "-out", _TMP_PEM, "4096",], stdout=subprocess.DEVNULL,
    )


def pause_until_complete(open_process: Optional[subprocess.Popen]):
    logger.info("pause_until_complete")
    if open_process is None:
        return

    while True:
        return_code = open_process.poll()
        if return_code is not None:
            click.echo(f"Return Code {return_code}")
            return return_code == 0


if __name__ == "__main__":
    provision()
