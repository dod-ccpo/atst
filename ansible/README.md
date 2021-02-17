# Intro

Ansible is a widely used, first class, config as code tool. Its an idempotent, stateless way to make source controlled, declarative, repeatable changes to config. yay.

To use ansible, the operator codes out his actions and applies them, like terraform, to a set of hosts, or subset of hosts.  We logically group reusable actions into `roles`,`plays`,`tasks` and then call them at the command line with variable values in the common places (env, file, cmd line args).

This is especially useful in unattended scenarios controlled by change management, source control and a task runner like AWX or CI/CD.  Security benefits include secrets/config at runtime.

Even though ATAT is completely containerized, its not immune to the benefits of ansible.  Providing a completely decoupled abstraction layer to Terraform increases its operationlization by giving us the ability to store configuration in an encrypted cloud store and enabling unattended, batch/scheduled execution of TF to stay continually compliant, avoiding drift and correcting manual changes to environments.



## Requirements


* `python` >= 3.8
  Python version 3.8 **must** be installed on your machine before installing `poetry`.
  You can download Python 3.8 [from python.org](https://www.python.org/downloads/)
  or use your preferred system package manager. Multiple versions of Python can exist on one
  computer, but 3.8 or newer is required for ATAT.

* `poetry`
  ATAT's Ansible package requires `poetry` to be installed for python dependency management. `poetry`
  will create the virtual environment that the app requires. [See
  `poetry`'s documentation for instructions on installing `poetry`](
  https://python-poetry.org/docs/#installation).

## Installation

To install Ansible and all of the necessary Python dependencies, run the following command in this directory:

```
poetry install --no-root
```

This will install the required version of Ansible and related Azure SDK dependencies.


## ATAT Use Cases
(Disclaimer: these prescribed set of commands will change as we iterate, along w/ this doc. If you run into issues, please reach out.)


A forward note;  The `deploy_tag` referenced below should be chosen wisely.  Its sole purpose is to guarantee repeatable deploys of terraform based on either an annotated git tag, a commit hash, or any other level of mapping of your Terraform code with the target Terraform the config intended for deploy.

### Bootstrap terraform variable values as secrets to azure KeyVault

This is designed for the scenario where you've been developing TF locally and haven't put anything in to keyvault.  Notice the `deploy_tag` is declared here. This is significant
because it is the secret name under which all the values of your variable.tf file will live

This should happen at the end of your local development session when you're ready to let TF be executed by a machine in the cloud.

`poetry run ansible-playbook ops.yml  --extra-vars "bootstrap_terraform=true deploy_tag='v0.0.1' tf_dir='/path/containing/tf_variables/file' vault_url='http://vault-url' vault_secret='secret' vault_client_id='client_id' vault_tenant='tenant' vault_subscription_id='subscription_id'" `

### Updating Terraform config values already in azure KeyVault

The modifications (today) are done atomically, in RESTful fashion.  Meaning, an update takes whats in your `variables.tf` and puts its contents under the `deploy_tag` secret name every time and it doesn't consider whats already in KeyVault.  

Another way to think about this update flow; It assumes on disk your `variables.tf` file is in the state of `n+x` w/ what lives in KeyVault for the chosen deploy tag.  

If you're unsure how out of sync your local `variables.tf` and KeyVault `deploy_tag` values are, hop down to the next use case to find out.

`poetry run ansible-playbook ops.yml  --extra-vars "bootstrap_terraform=true deploy_tag='v0.0.2' tf_dir='/path/containing/tf_variables/file' vault_url='http://vault-url' vault_secret='secret' vault_client_id='client_id' vault_tenant='tenant' vault_subscription_id='subscription_id'" `


## Verifying whats in KeyVault with whats in `variables.tf`

You can use this as a reference to update your current `variables.tf` or just verify that your next push is additive/destructive in the way you intend.

If thats not true or you're unsure, the step after this will show you how to pull down current state to disk in the form of `retrieved.[deploy_tag].tfvars.json`.  

Notice `secrets_to_file` is defined.

`poetry run ansible-playbook ops.yml --extra-vars "secrets_to_file=true deploy_tag='v0.0.2' tf_dir='/path/containing/tf_variables/file' vault_url='http://vault-url' vault_secret='secret' vault_client_id='client_id' vault_tenant='tenant' vault_subscription_id='subscription_id'"`


## Usage Example

I won't recreate the docs, but an example ansible run of something that affects config/runs a playbook looks like:

`poetry run ansible-playbook play.yml --extra-vars "var_1='val1' ... var_2='val2'" [OPTIONS]`


## General Use Case Examples

Classically, ops engineers write imperative scripts to carry out tasks, for example:

```
#!/bin/bash
mkdir ./some_dir

```

This is hard to execute at scale and there's no guarantee the command will succeed.

In ansible, as part of a play for a larger config, called a `role` the command can be assigned to all or a subset of hosts across an entire estate.
```
- name: Create a directory if it does not exist
  file:
    path: /etc/some_directory
    state: directory
    mode: '0755'
```


## A more specific use case

### Bridging the gap between developing terraform and operationlizing it.

A human has to be involved at some point when writing terraform. Lets say you're adding a new variable and value to an existing TF like:

```
variables.tf:

variable new_vaccines {

  type= list
  value = ['x-10','y-123','zz-top']
}

```

In our set of ansible, there's a task in the azure role that will parse variables.tf for values and atomically add them to the keyvault. To do that you'd perform the following:

`poetry run ansible-playbook site.yml --extra-vars "bootstrap_terraform=true deploy_tag='v0.0.1' tf_dir='/path/to/terraform/providers/pwdev' vault_url='some_vault_url' vault_secret='some_secret' vault_client_id='some_client_id' vault_tenant='some_tenant'" `


If I want to refresh the local variables.tf file, there's another task that will pull variables from key vault and populate a json file. You can manually port the returned json to HCL if you'd like but the idea is that machines run terraform in production, hence json. To retrieve the current variable values:


`poetry run ansible-playbook site.yml --extra-vars "ops=true secrets_to_file=true deploy_tag='v0.0.1' tf_dir='/path/to/terraform/' vault_url='some_url' vault_secret='some_secret' vault_client_id='some_client_id' vault_tenant='some_tenant' vault_subscription_id='some_subscription'"`

In out case, secrets achieve vault and csp agnostic versions by storing all terraform config under the key `deploy_tag`, this way we can tie terraform releases to their respective secrets and have repeatable deployments.

There are lots more possibilities and i will be adding here in the future.
