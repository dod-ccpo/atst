import json
import logging
import os
import shutil
import subprocess
import sys
from os import path
from pprint import pprint

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
    "--ops_registry",
    help="Full URI of the container registry that after bootstrapping, should have rhel, rhel-py, and ops images - envvar: OPS_REGISTRY",
    prompt="Full URI of container registry eg: cloudzeroopsregistry${var.namespace}.azurecr.io",
    envvar="OPS_REGISTRY",
)
@click.option(
    "--namespace",
    help="Namespacing of your environment - envvar: NAMESPACE",
    envvar="NAMESPACE",
)
@click.option(
    "--atat_registry",
    help="Short name of the container registry that k8s will have access to - envvar: ATAT_REGISTRY",
    prompt="Short name of the atat container registry eg:cloudzeroregistry",
    envvar="ATAT_REGISTRY",
)
@click.option(
    "--atat-image-tag",
    default="latest",
    help="Set the tag applied to the atat image that will be build",
)
@click.option("--atat-commit-sha", help="")
@click.option(
    "--nginx-image-tag",
    default="latest",
    help="Set the tag applied to the nginx image that will be build",
)
@click.option("--git-sha", help="The git sha of the current commit")
@click.option(
    "--config-azcli/--no-config-azcli",
    default=True,
    help="Whether to try and run the az login w/ the service principle so we can install the aks plugins",
)
@click.option(
    "--ironbank-account",
    help="Account for grabbing images from ironbank",
    envvar="IRONBANK_ACCOUNT",
)
@click.option(
    "--ironbank-secret",
    help="Secret for grabbing images from ironbank",
    envvar="IRONBANK_SECRET",
)
@click.option(
    "--ironbank-nginx-tag",
    help="nginx tag for image from ironbank",
    default="1.19.2",
    envvar="IRONBANK_NGINX_TAG",
)
def deploy(
    sp_client_id,
    sp_client_secret,
    subscription_id,
    tenant_id,
    namespace,
    ops_registry,
    atat_registry,
    atat_image_tag,
    nginx_image_tag,
    config_azcli,
    git_sha,
    atat_commit_sha,
    ironbank_account,
    ironbank_secret,
    ironbank_nginx_tag,
):
    setup(
        sp_client_id,
        sp_client_secret,
        subscription_id,
        tenant_id,
        namespace,
        config_azcli,
    )
    import_images(ops_registry, atat_registry)
    build_atat(atat_registry, git_sha, atat_image_tag)
    build_nginx(
        atat_registry,
        nginx_image_tag,
        ironbank_account,
        ironbank_secret,
        ironbank_nginx_tag,
    )

    os.environ["ARM_CLIENT_ID"] = sp_client_id
    os.environ["ARM_CLIENT_SECRET"] = sp_client_secret
    os.environ["ARM_SUBSCRIPTION_ID"] = subscription_id
    os.environ["ARM_TENANT_ID"] = tenant_id

    tf_output_dict = collect_terraform_outputs()

    # Create template output directory
    if os.path.exists(".out"):
        shutil.rmtree(".out")
    os.mkdir(".out")

    env = Environment(
        loader=FileSystemLoader("deployment_templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Gather the template variables
    template_variables = {
        **tf_output_dict,
        **{
            "sp_client_id": sp_client_id,
            "sp_client_secret": sp_client_secret,
            "subscription_id": subscription_id,
            "tenant_id": tenant_id,
            "atat_image_tag": atat_image_tag,
            "nginx_image_tag": nginx_image_tag,
            "application_container_image": f"{atat_registry}.azurecr.io/atat:{atat_image_tag}",
            "nginx_container_image": f"{atat_registry}.azurecr.io/nginx:{nginx_image_tag}",
        },
    }

    pprint(template_variables)

    # Generate the output files
    for path in os.listdir("deployment_templates"):
        template = env.get_template(path)
        with open(f".out/{path}", "w") as output_file:
            output_file.write(template.render(**template_variables))

    subprocess.run(["kubectl", "apply", "--kustomize=.out/"])
    subprocess.run(["kubectl", "-n", namespace, "get", "services"])


def setup(
    sp_client_id, sp_client_secret, subscription_id, tenant_id, namespace, config_azcli
):
    if config_azcli:
        configure_azcli(
            sp_client_id=sp_client_id,
            sp_client_secret=sp_client_secret,
            tenant_id=tenant_id,
            namespace=namespace,
        )


def configure_azcli(sp_client_id, sp_client_secret, tenant_id, namespace):
    cmd = [
        "az",
        "login",
        "--service-principal",
        "--username",
        sp_client_id,
        "--password",
        sp_client_secret,
        "--tenant",
        tenant_id,
    ]
    print(cmd)
    subprocess.run(cmd).check_returncode()
    subprocess.run("az extension add --name aks-preview".split()).check_returncode()
    subprocess.run("az extension update --name aks-preview".split()).check_returncode()
    subprocess.run(
        "az feature register --name AKS-AzurePolicyAutoApprove --namespace Microsoft.ContainerService".split()
    ).check_returncode()
    subprocess.run(
        "az provider register --namespace Microsoft.ContainerService".split()
    ).check_returncode()
    subprocess.run(
        f"az aks get-credentials -g cloudzero-vpc-{namespace} -n cloudzero-private-k8s-{namespace}".split()
    ).check_returncode()


def import_images(ops_registry, atat_registry):
    cmd = [
        "az",
        "acr",
        "import",
        "--name",
        atat_registry,
        "--source",
        f"{ops_registry}/rhel-py:latest",
    ]
    # TODO: Not checking the return code, because it fails if already imported.
    subprocess.run(cmd)


def build_atat(atat_registry, git_sha, atat_image_tag):
    cmd = [
        "az",
        "acr",
        "build",
        "--registry",
        atat_registry,
        "--build-arg",
        f"IMAGE={atat_registry}.azurecr.io/rhel-py:latest",
        "--image",
        f"atat:{atat_image_tag}",
        "--file",
        "../../Dockerfile",
        "../..",
    ]
    # TODO: Make this async
    subprocess.run(cmd).check_returncode()


def build_nginx(
    atat_registry,
    nginx_image_tag,
    ironbank_account,
    ironbank_secret,
    ironbank_nginx_tag,
):
    cmd = [
        "az",
        "acr",
        "import",
        "--name",
        atat_registry,
        "--source",
        f"registry1.dso.mil/ironbank/opensource/nginx/nginx:{ironbank_nginx_tag}",
        "--image",
        f"nginx:{nginx_image_tag}",
        "--username",
        ironbank_account,
        "--password",
        ironbank_secret,
    ]
    # TODO: Make this async
    subprocess.run(cmd).check_returncode()


def collect_terraform_outputs():
    """Collects terraform output into name/value dict to pass as json to ansible"""
    logger.info("collect_terraform_outputs")

    cwd = path.join("../", "../", "terraform", "providers", "application_env")

    result = subprocess.run(
        "terraform output -json".split(), cwd=cwd, capture_output=True
    )
    result.check_returncode()
    output = json.loads(result.stdout.decode("utf-8"))

    return {k: v["value"] for k, v in output.items() if type(v["value"]) in [str, int]}


if __name__ == "__main__":
    deploy()
