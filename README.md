# ATAT

[![Build Status](https://circleci.com/gh/dod-ccpo/atst.svg?style=svg)](https://circleci.com/gh/dod-ccpo/atst)

## Description

This is the user-facing web application for ATAT.

## Installation

### System Requirements
ATAT uses the [Scripts to Rule Them All](https://github.com/github/scripts-to-rule-them-all)
pattern for setting up and running the project. The scripts are located in the
`script` directory and use script fragments in the
[scriptz](https://github.com/dod-ccpo/scriptz) repository that are shared across
ATAT repositories.

General instructions follow; however, there are
[specific instructions](/docs/WindowsSubsystemLinux.md) available for running
using the Windows Subsystem for Linux.

Before running the setup scripts, a couple of dependencies need to be installed
locally:

* `python` == 3.7.3
  Python version 3.7.3 **must** be installed on your machine before installing `poetry`.
  You can download Python 3.7.3 [from python.org](https://www.python.org/downloads/)
  or use your preferred system package manager. Multiple versions of Python can exist on one
  computer, but 3.7.3 is required for ATAT.

* `poetry`
  ATAT requires `poetry` to be installed for python dependency management. `poetry`
  will create the virtual environment that the app requires. [See
  `poetry`'s documentation for instructions on installing `poetry`](
  https://python-poetry.org/docs/#installation).

* `yarn`
  ATAT requires `yarn` for installing and managing Javascript
  dependencies: https://yarnpkg.com/en/

* `postgres` >= 9.6
  ATAT requires a PostgreSQL instance (>= 9.6) for persistence. Have PostgresSQL installed
  and running on the default port of 5432. (A good resource for installing and running
  PostgreSQL for Macs is [Postgres.app](https://postgresapp.com/). Follow the instructions,
  including the optional Step 3, and add `/Applications/Postgres.app/Contents/Versions/latest/bin`
  to your `PATH` environment variable.) You can verify that PostgresSQL is running
  by executing `psql` and ensuring that a connection is successfully made.

* `redis`
  ATAT also requires a Redis instance for session management. Have Redis installed and
  running on the default port of 6379. You can ensure that Redis is running by
  executing `redis-cli` with no options and ensuring a connection is succesfully made.

* [`entr`](http://eradman.com/entrproject/)
  This dependency is optional. If present, the queue worker process will hot
  reload in development.

* `node` == 10
  This is a requirement of [node-sass](https://github.com/sass/node-sass).  For macOS, use brew to install:
  ```
  brew install node@10
  ```

  You will have to either create symlinks to the binaries or update the path.  Both are probably not necessary:
  ```
  brew link --force --overwrite node@10
  echo 'export PATH="/usr/local/opt/node@10/bin:$PATH"' >> ~/.zshrc
  ```

* `xmlsec1`
  This is a downstream requirement of [python3-saml](https://github.com/onelogin/python3-saml). For macOS, use brew to install:
  ```
  brew install libxmlsec1
  ```

### Cloning
This project contains git submodules. Here is an example clone command that will
automatically initialize and update those modules:

    git clone --recurse-submodules git@github.com:dod-ccpo/atst.git

If you have an existing clone that does not yet contain the submodules, you can
set them up with the following command:

    git submodule update --init --recursive

### Setup
This application uses `poetry` to manage Python dependencies and a virtual
environment. Instead of the classic `requirements.txt` file, `poetry` uses a
`pyproject.toml` and `poetry.lock`, making it more similar to other modern package managers like yarn or mix.

To perform the installation, run the setup script:

    script/setup

The setup script creates the virtual environment, and then calls script/bootstrap
to install all of the Python and Node dependencies and run database migrations.

To enter the virtualenv manually (a la `source .venv/bin/activate`):

    poetry shell

If you want to automatically load the virtual environment whenever you enter the
project directory, take a look at [direnv](https://direnv.net/).  An `.envrc`
file is included in this repository.  direnv will activate and deactivate
virtualenvs for you when you enter and leave the directory.

### Troubleshooting Setup

If you have a new postgres installation you might encounter
errors about the `postgres` role not existing. If so, run:

```
createuser -s postgres
```

If `script/setup` complains that the database does not exist,
run:

```
createdb atat
```

If Celery is throwing a "Too many open files" error, you may need to increase the machine's ulimit:

```
ulimit -n 1024
```

## Running (development)

To start the app locally in the foreground and watch for changes:

    script/server

After running `script/server`, the application is available at
[`http://localhost:8000`](http://localhost:8000).

In some cases, you may be required to run the localhost server via https. In order to do this, you can run:

    script/secure_server

The application will then be available  at
[`https://localhost:8000`](https://localhost:8000). You will likely be presented with a warning about a non-secure connection at this point, most browsers have the option of bypassing this warning by checking the `advanced` or `more info` links on the error page.

If starting the secure server fails, you may need to generate the local certificates first:

    script/create_local_certs

### Users

When the ALLOW_LOCAL_ACCESS setting is enabled, there are six mock users for development:

- Sam (a CCPO)
- Amanda
- Brandon
- Christina
- Dominick
- Erica

To log in as one of them, navigate to `/login-local?username=<lowercase name>`.
For example `/login-local?username=amanda`.

Additionally, this endpoint can be used to log into any real users in the dev environments by providing their DoD ID:
`/login-local?dod_id=1234567890123`

With ALLOW_LOCAL_ACCESS enabled, you can create new users by passing first name, last name, and DoD ID query parameters to `/dev-new-user` like so:
```
/dev-new-user?first_name=Harrold&last_name=Henderson&dod_id=1234567890123
```
And it will create the new user, sign in as them, and load their profile page to fill out the rest of the details.

Once this user is created, you can log in as them again the future using the DoD ID dev login endpoint documented above.

**Federated Authentication with Azure**

The `/login-dev` routes require that you have a valid account in the Azure Active Directory tenant and authenticate against it.

### Seeding the database

We have a helper script that will seed the database with requests, portfolios and
applications for all of the test users:

`poetry run python script/seed_sample.py`

### Email Notifications

To send email, the following configuration values must be set:

```
MAIL_SERVER = <SMTP server URL>
MAIL_PORT = <SMTP server port>
MAIL_SENDER = <Login name for the email account and sender address>
MAIL_PASSWORD = <login password for the email account>
MAIL_TLS = <Boolean, whether TLS should be enabled for outgoing email. Defaults to false.>
```

When the `DEBUG` environment variable is enabled and the app environment is not
set to production, sent email messages are available at the `/messages` endpoint.
Emails are not sent in development and test modes.

### File Uploads and Downloads

Testing file uploads and downloads locally requires a few configuration options.

In the flask config (`config/base.ini`, perhaps):

```
CSP=< azure | mock>

AZURE_STORAGE_KEY=""
AZURE_STORAGE_ACCOUNT_NAME=""
AZURE_TO_BUCKET_NAME=""
```

There are also some build-time configuration that are used by parcel. Add these to `.env.local`, and run `rm -r .cache/` before running `yarn build`:

```
CLOUD_PROVIDER=<azure | mock>
AZURE_STORAGE_ACCOUNT_NAME=""
AZURE_CONTAINER_NAME=""
```

## Testing

Tests require a test database:

```
createdb atat_test
```

To run lint, static analysis, and Python unit tests:

    script/test

To run only the Python unit tests:

    poetry run python -m pytest
**Integration tests with the Hybrid Interface**

Integration tests that use the hybrid cloud provider are skipped by default and should be run on their own, as some of the required hybrid configuration values may cause certain non-hybrid tests to fail. As a result, it's recommended that you do not `EXPORT` these hybrid config values into your shell environment, but instead load them only for that command with something like the following:

```
env $(cat .env.hybrid | xargs) poetry run pytest --no-cov --hybrid tests/domain/cloud/test_hybrid_csp.py
```
The config values required by the hybrid tests are outlined in the [Hybrid Configuration](#hybrid-configuration) section. Note that the `--hybrid` parameter is also required for hybrid tests to run.

This project also runs Javascript tests using jest. To run the Javascript tests:

    yarn test

To re-run the Javascript tests each time a file is changed:

    yarn test:watch

To generate coverage reports for the Javascript tests:

    yarn test:coverage

## Configuration

### Setting Configuration

All config settings must be declared in "config/base.ini", even if they are null. Configuration is set in the following order:

1. Settings from "config/base.ini" are read in and applied.
2. If FLASK_ENV is set as an environment variable and there is an INI file with a matching name, that INI file is read in and applied. For instance, if FLASK_ENV is set to "prod" and a "prod.ini" file exists, those values will be applied and will override any values set by the base.ini.
3. MSFT supports an [OSS Kubernetes plugin](https://github.com/Azure/kubernetes-keyvault-flexvol) for mounting objects from Azure Key Vault into containers. We use this feature to store application secrets in a Key Vault instance and set them in the container at runtime (see "deploy/README.md" for more details). This is done by mounting the secrets into a known directory and specifying it with an environment variable, OVERRIDE_CONFIG_DIRECTORY. If OVERRIDE_CONFIG_DIRECTORY is set, ATAT will do the following:
  1. Find the specified directory. For example, "/config"
  1. Search for files in that directory with names matching known settings. For example, a file called "AZURE_STORAGE_ACCOUNT_NAME".
  1. Read in the contents of those files and set the content as the value for that setting. These will override any values previously set. For example, if the file "AZURE_STORAGE_ACCOUNT_NAME" has the content "my-azure-account-name", that content will be set as the value for the AZURE_STORAGE_ACCOUNT_NAME setting.
4. Finally, ATAT will check for the presence of environment variables matching all known config values. If a matching environment variable exists, its value will override whatever value was previously set.

### Config Guide

#### General Config

- `ALLOW_LOCAL_ACCESS`: Enables additional development routes that will allow developers working locally and automated tools (like functional end-user tests) to authenticate
- `ASSETS_URL`: URL to host which serves static assets (such as a CDN).
- `APP_SSL_CERT_PATH`: Path to the self-signed SSL certificate for running the app in secure mode.
- `APP_SSL_KEY_PATH`: Path to the self-signed SSL certificate key for running the app in secure mode.
- `AZURE_STORAGE_ACCOUNT_NAME`: The name for the Azure blob storage account.
- `AZURE_BILLING_ACCOUNT_NAME`: The ID for the root Azure billing account. This can be found by going to the properties panel of the root invoice section within the Azure portal.
- `AZURE_CALC_CLIENT_ID`: The client id used to generate a token for the Azure pricing calculator
- `AZURE_CALC_RESOURCE`: The resource URL used to generate a token for the Azure pricing calculator
- `AZURE_CALC_SECRET`: The secret key used to generate a token for the Azure pricing calculator
- `AZURE_CALC_URL`: The redirect URL for the Azure pricing calculator.
- `AZURE_LOGIN_URL`: The URL used to login for an Azure instance.
- `AZURE_POWERSHELL_CLIENT_ID`: This client id is set to a value [hardcoded by Microsoft](https://docs.microsoft.com/en-us/azure-stack/user/azure-stack-rest-api-use?view=azs-2008#example) for making API calls
- `AZURE_STORAGE_KEY`: A valid secret key for the Azure blob storage account.
- `AZURE_TO_BUCKET_NAME`: The Azure blob storage container name for task order uploads.
- `BLOB_STORAGE_URL`: URL to Azure blob storage container.
- `CA_CHAIN`: Path to the CA chain file.
- `CDN_ORIGIN`: URL for the origin host for asset files.
- `CELERY_DEFAULT_QUEUE`: String specifying the name of the queue that background tasks will be added to.
- `CELERYBEAT_SCHEDULE_VALUE`: Integer specifying a default value of how many seconds wait between scheduled celery beat tasks. All celery beat tasks use this value.
- `CONTRACT_END_DATE`: String specifying the end date of the JEDI contract. Used for task order validation. Example: 2019-09-14
- `CONTRACT_START_DATE`: String specifying the start date of the JEDI contract. Used for task order validation. Example: 2019-09-14.
- `CSP`: String specifying the cloud service provider to use. Acceptable values: "azure", "mock", "mock-csp" and "hybrid". If using the hybrid provider due to the injunction, set it to "hybrid".
- `DEBUG`: Boolean. A truthy value enables Flask's debug mode. https://flask.palletsprojects.com/en/1.1.x/config/#DEBUG
- `DEBUG_SMTP`: [0,1,2]. Use to determine the debug logging level of the mailer SMTP connection. `0` is the default, meaning no extra logs are generated. `1` or `2` will enable debug logging. See [official docs](https://docs.python.org/3/library/smtplib.html#smtplib.SMTP.set_debuglevel) for more info.
- `ENVIRONMENT`: String specifying the current environment. Acceptable values: "dev", "prod".
- `LIMIT_CONCURRENT_SESSIONS`: Boolean specifying if users should be allowed only one active session at a time.
- `LOG_JSON`: Boolean specifying whether app should log in a json format.
- `MAIL_PASSWORD`: String. Password for the SMTP server.
- `MAIL_PORT`: Integer. Port to use on the SMTP server.
- `MAIL_SENDER`: String. Email address to send outgoing mail from.
- `MAIL_SERVER`: The SMTP host
- `MAIL_TLS`: Boolean. Use TLS to connect to the SMTP server.
- `MICROSOFT_TASK_ORDER_EMAIL_ADDRESS`: String. Email address for Microsoft to receive PDFs of new and updated task orders.
- `PERMANENT_SESSION_LIFETIME`: Integer specifying how many seconds a user's session can stay valid for. https://flask.palletsprojects.com/en/1.1.x/config/#PERMANENT_SESSION_LIFETIME
- `PGDATABASE`: String specifying the name of the postgres database.
- `PGHOST`: String specifying the hostname of the postgres database.
- `PGPASSWORD`: String specifying the password of the postgres database.
- `PGPORT`: Integer specifying the port number of the postgres database.
- `PGSSLMODE`: String specifying the ssl mode to use when connecting to the postgres database. https://www.postgresql.org/docs/9.1/libpq-ssl.html
- `PGSSLROOTCERT`: Path to the root SSL certificate for the postgres database.
- `PGUSER`: String specifying the username to use when connecting to the postgres database.
- `PORT`: Integer specifying the port to bind to when running the flask server. Used only for local development.
- `REDIS_HOST`: String. Hostname for the redis server, including port number.
- `REDIS_PASSWORD`: String. Password or authentication key for the Redis server.
- `REDIS_SSLMODE`: String. Can be one of "required", "optional", or "none". Determines whether the client will perform a certificate verification of the server. (Implemented in redis-py with https://docs.python.org/3/library/ssl.html#ssl.SSLContext.verify_mode)
- `REDIS_SSLCHECKHOSTNAME`: Boolean. Specifies whether to verify that the Redis server hostname matches what's on the cert the server presents. (Implemented in redis-py with https://docs.python.org/3/library/ssl.html#ssl.SSLContext.check_hostname)
- `REDIS_TLS`: Boolean. Determines whether the Redis client should use SSL/TLS.
- `REDIS_USER`: String. The Redis username (generally blank).
- `SAML_ACS`: Fully qualified URI for the URL that the SAML Identity Provider will redirect to after successful authentication
- `SAML_ENTITY_ID`: Fully qualified URI that ATAT will invoke SAML authentication from
- `SAML_IDP_URI`: URI of the SAML IdP Metadata, will be fetched and used to configure SAML calls
- `SAML_SLS`: Fully qualified URI that ATAT will invoke SAML logout from
- `SAML_DEV_ACS`: Fully qualified URI for the URL that the SAML Identity Provider used for developer login (only used if `FLASK_ENV` isn't `prod`)
- `SAML_DEV_ENTITY_ID`: Fully qualified URI that ATAT will invoke developer SAML authentication from (only used if `FLASK_ENV` isn't `prod`)
- `SAML_DEV_SLS`: Fully qualified URI that ATAT will invoke developer SAML logout from (only used if `FLASK_ENV` isn't `prod`)
- `SAML_DEV_IDP_URI`: URI of the developer SAML IdP Metadata, will be fetched and used to configure SAML calls (only used if `FLASK_ENV` isn't `prod`)
- `SAMl_LOGIN_DEV`: Boolean that defines if Azure Fed Auth will be required to log in using the developer login route. Defaults to `False`  (only used if `FLASK_ENV` isn't `prod`)
- `SECRET_KEY`: String key which will be used to sign the session cookie. Should be a long string of random bytes. https://flask.palletsprojects.com/en/1.1.x/config/#SECRET_KEY
- `SERVER_NAME`: Hostname for ATAT. Only needs to be specified in contexts where the hostname cannot be inferred from the request, such as Celery workers. https://flask.palletsprojects.com/en/1.1.x/config/#SERVER_NAME
- `SERVICE_DESK_URL`: The URL for the service desk.  This is the site that will be displayed when the Support button is pressed.
- `SESSION_COOKIE_NAME`: String value specifying the name to use for the session cookie. https://flask.palletsprojects.com/en/1.1.x/config/#SESSION_COOKIE_NAME
- `SESSION_COOKIE_DOMAIN`: String value specifying the name to use for the session cookie. This should be set to the root domain so that it is valid for both the main site and the authentication subdomain. https://flask.palletsprojects.com/en/1.1.x/config/#SESSION_COOKIE_DOMAIN
- `SESSION_KEY_PREFIX`: A prefix that is added before all session keys: https://pythonhosted.org/Flask-Session/#configuration
- `SESSION_TYPE`: String value specifying the cookie storage backend. https://pythonhosted.org/Flask-Session/
- `SESSION_COOKIE_SECURE`: https://flask.palletsprojects.com/en/1.1.x/config/#SESSION_COOKIE_SECURE
- `SESSION_USE_SIGNER`: Boolean value specifying if the cookie sid should be signed.
- `SIMULATE_API_FAILURES`: Boolean value specifying if a non-production CSP should randomly produce API failures.
- `SQLALCHEMY_ECHO`: Boolean value specifying if SQLAlchemy should log queries to stdout.
- `STATIC_URL`: URL specifying where static assets are hosted.
- `USE_AUDIT_LOG`: Boolean value describing if ATAT should write to the audit log table in the database. Set to "false" by default for performance reasons.
- `WTF_CSRF_ENABLED`: Boolean value specifying if WTForms should protect against CSRF. Should be set to "true" unless running automated tests.

#### Hybrid Configuration

Values where "[Testing only]" is mentioned are only required for running the Hybrid test suite, **not** for using the Hybrid interface for a running instance of ATAT.

Configuration variables that are needed solely to run Hybrid tests are in the `[hybrid]` section of the base configuration file.
- `AZURE_BILLING_PROFILE_ID`: ID of the billing profile used for Cost Management queries with the Hybrid interface.
- `AZURE_SUBSCRIPTION_CREATION_CLIENT_ID`: [Testing only] Client ID of an app registration in the root tenant used for subscription integration tests
- `AZURE_SUBSCRIPTION_CREATION_SECRET`: [Testing only] Secret key for the app registration associated with the `AZURE_SUBSCRIPTION_CREATION_CLIENT_ID`
- `AZURE_HYBRID_REPORTING_CLIENT_ID`: Client ID of an app registration with an "Invoice Section Reader" role for the invoice section defined by AZURE_INVOICE_SECTION_ID
- `AZURE_HYBRID_REPORTING_SECRET`: Secret key for the app registration associated with the `AZURE_HYBRID_REPORTING_CLIENT_ID`
- `AZURE_HYBRID_TENANT_DOMAIN`: The domain of the hybrid tenant
- `AZURE_HYBRID_TENANT_ID`: ID of the tenant used to store resources provisioned during Hybrid tests
- `AZURE_INVOICE_SECTION_ID`: ID of the invoice section used for Cost Management queries with the Hybrid interface.
- `AZURE_TENANT_ADMIN_PASSWORD`: Password associated with the "root" tenant id used in the Hybrid Cloud Provider
- `AZURE_TENANT_ADMIN_USERNAME`: Username of an admin user associated with the "root" tenant id used in the Hybrid Cloud Provider
- `AZURE_USER_OBJECT_ID`: Object Id of an admin user associated with the "root" tenant id used in the Hybrid Cloud Provider


### CircleCI Configuration

CircleCI is our current CI/CD provider. The following variables need to be set in the project settings for CI/CD to run:

- `AZURE_STORAGE_ACCOUNT_NAME`: The name of the Azure Storage Account used for task orders
- `AZURE_REGISTRY`: The name of the Azure Container Registry for ATAT docker images
- `AZURE_SERVER_NAME`: The domain name of the same Azure Container Registry as AZURE_REGISTRY (e.g. cloudzeroregistry.azurecr.io)
- `AZURE_SP`: The human-readable name of a Service Principal with the "Azure Kubernetes Service Cluster User Role" to the AKS cluster and the "AcrPush" role to the Azure Container Registry
- `AZURE_SP_PASSWORD`: A client secret for the AZURE_SP
- `AZURE_SP_TENANT`: The Azure Active Directory tenant ID the AZURE_SP is associated with (same as TENANT_ID)
- `CLUSTER_NAME`: The human-readable name of the Azure Kubernetes Cluster (e.g., cloudzero-dryrun-k8s)
- `GI_API_KEY`: An API key for Ghost Inspector (see [its README](./uitests/README.md))
- `GI_SUITE`: An ID for the suite of Ghost Inspector tests to be run (see [its README](./uitests/README.md))
- `KEYVAULT_NAME`: The name of the Key Vault that ATAT will source its secret config from
- `NGROK_TOKEN`: A token to allow Ghost Inspector to create an NGROK tunnel to a container instance of ATAT (see [the UI tests README](./uitests/README.md))
- `RESOURCE_GROUP`: The resource group of the AKS cluster
- `TENANT_ID`: The Azure Active Directory tenant ID ATAT's infrastructure is associated with
- `VMSS_CLIENT_ID`: The client ID of the managed identity associated with the Virtual Machine Scale Set underlying the AKS cluster

## UI Test Automation

AT-AT uses [Ghost Inspector](https://app.ghostinspector.com/), a testing PaaS
for UI test automation and as a form of integration testing.
These tests do not run locally as part of the regular test suite,
but they do run in CI.

Ghost Inspector was developed to make it easier to create, maintain, and
execute UI tests than vanilla Selenium. Ghost Inspector tests and steps can
be exported to files that the Selenium IDE can import. We export these tests/steps
regularly and archive them with the AT-AT codebase in the `uitests` directory.

For further information about Ghost Inspector and its use in AT-AT, check out [its README](./uitests/README.md)
in the `uitests` directory.

## Notes

Jinja templates are like mustache templates -- add the
following to `~/.vim/filetype.vim` for syntax highlighting:

    :au BufRead *.html.to set filetype=mustache


## Icons
To render an icon, use

```jinja
{% import "components/icon.html" %}
{{ Icon("icon-name", classes="css-classes") }}
```

where `icon-name` is the filename of an svg in `static/icons`.

All icons used should be from the Noun Project, specifically [this collection](https://thenounproject.com/monstercritic/collection/tinicons-a-set-of-tiny-icons-perfect-for-ui-elemen/) if possible.

SVG markup should be cleaned an minified, [Svgsus](http://www.svgs.us/) works well.

## Deployment

### Docker build

For testing the Docker build, the repo includes a `docker-compose.yml` that will run the app container with an NGINX server in front of it. To run it, you will need `docker` and `docker-compose` installed, then:

```
docker-compose up
```

The app will be available on http://localhost:8080.

The build assumes that you have redis and postgres running on their usual ports on your host machine; it does not pull images for those services. The docker-compose build is not suitable for development because it does not mount or reload working files.

Note that the uWSGI config used for this build in the repo root is symlinked from deploy/azure/uwsgi.ini. See the Kubernetes README in deploy/README.md for details.

### Local login

The `/login-local` endpoint is protected by HTTP basic auth by uWSGI in the docker container (https://uwsgi-docs.readthedocs.io/en/latest/InternalRouting.html#basicauth).

To enable this in a deployed environment, you must set ALLOW_LOCAL_ACCESS to true and provide a password file to the container my mounting a volume or other means. The uWSGI configuration expects to find the password file at `/config/localpassword`.

You can generate a password with the htpassword. In this example, the command will generate a "localpassword" file in the current directory for a user called "atat":

```
htpasswd -cd ./localpassword atat
```

It will prompt you to enter a password, then produce the password file. Note that the `-d` flag is necessary, per the uWSGI documentation linked above.

## Secrets Detection

This project uses [detect-secrets](https://github.com/Yelp/detect-secrets) to help prevent secrets from being checked into source control. Secret detection is run automatically as part of `script/test` and can be run separately with `script/detect_secrets`.

If you need to check in a file that raises false positives from `detect-secrets`, you can add it to the whitelist. Run:

```
poetry run detect-secrets scan --no-aws-key-scan --no-stripe-scan --no-slack-scan --no-artifactory-scan --update .secrets.baseline
```

and then:

```
poetry run detect-secrets audit .secrets.baseline
```

The audit will open an interactive prompt where you can whitelist the file. This is useful if you're checking in an entire file that looks like or is a secret (like a sample PKI file).

Alternatively, you can add a `# pragma: allowlist secret` comment to the line that raised the false positive. See the [detect-secret](https://github.com/Yelp/detect-secrets#inline-allowlisting) docs for more information.

It's recommended that you add a pre-commit hook to invoke `script/detect_secrets`. Add the example below or something equivalent to `.git/hooks/pre-commit`:

```
#!/usr/bin/env bash

if ./script/detect_secrets staged; then
  echo "secrets check passed"
else
  echo -e "**SECRETS DETECTED**"
  exit 1
fi
```

Also note that if the line number of a previously whitelisted secret changes, the whitelist file, `.secrets.baseline`, will be updated and needs to be committed.

## How to build the RHEL Python base image

First create two files, containing a RedHat username and password respectively. A free RedHat account is needed to access certain required package repositories.

- redhat_username.secret
- redhat_password.secret


Make sure you're logged into the appropriate container registry. We're using `cloudzerodryrunregistry` as the example here.

```
az acr login -n cloudzerodryrunregistry
```

Then run the build script:

```
env CONTAINER_REGISTRY=cloudzerodryrunregistry.azurecr.io ./ops/build-docker-image-python-base.sh
```

Then publish the image. Start by tagging it with the appropriate registry.
```
docker tag atst:rhel-py cloudzerodryrunregistry.azurecr.io/rhel-py:latest
```

Then push!

```
docker push cloudzerodryrunregistry.azurecr.io/rhel-py
```

## How to generate the Under Maintenance page

The script uses the existing templating system. This means that you'll need to have a functioning local install with
the redis and postres running. Additionally, this script will need to ran from the project's root directory.

General usage for the UM script would include a location for the output.

```
poetry run python script/generate_under_maintenance.py --output ./
```

## SonarCloud

To manually run sonar-scanner you will need a token.  On [The SonarCloud Account Security](https://sonarcloud.io/account/security/) page create a token and export it to the environment variable `SONAR_TOKEN`.  

```
export SONAR_TOKEN=< sonar token >
```

Now you will be able to run the scanner script.

```
script/sonar_scanner
````

The sonar-scanner script will generate a coverage report for Python and JavaScript files.  Any value that might need to be updated (i.e. code exception or coverage exceptions) can be done in the `sonar-project.properties` file
