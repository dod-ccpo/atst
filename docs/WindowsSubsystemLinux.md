# Configuring Windows Subsystem for Linux to run the local server

These instructions cover setting up the local server on Windows Subsystem for
Linux, specifically focusing on Ubuntu 20.04. For instructions on initial
installation and configuration of the Windows Subsystem for Linux, consult
the [Microsoft Documentation](https://docs.microsoft.com/en-us/windows/wsl/install-win10).

## Updating packages

If you are using a fresh WSL installation, don't forget to update your package
cache and update all installed packages.

```
$ sudo apt update
$ sudo apt upgrade
```

## Install prerequisites

Some prerequisites need to be installed prior to the following steps:

```
$ sudo apt install git python3 python-is-python3
```

## Python Setup

Currently, ATAT requires specifically Python 3.7.3. Since Ubuntu currently
includes Python 3.8 in the repositories, Python 3.7.3 must be installed through
external means. This can be done with [`pyenv`](https://github.com/pyenv/pyenv).

1. Install the [prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment)
   for building Python
   ```
   $ sudo apt-get update; sudo apt-get install --no-install-recommends make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
   ```
1. Checkout `pyenv`
   ```
   $ git clone https://github.com/pyenv/pyenv.git ~/.pyenv
   ```
1. Add `pyenv` to `~/.bashrc`:
   ```
    $ echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    $ echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    $ echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.bashrc
    ```
1. Install Python 3.7.3: `pyenv install 3.7.3`

If you get an error that `pyenv` is not installed, re-execute your shell by
running the following and trying again:

```
$ exec "$SHELL"
```

Temporarily enter the `pyenv` environment for Python 3.7.3 and install Poetry:

```
$ pyenv shell 3.7.3
$ pip install poetry 
```

## Package Installation

All of Redis, NodeJS, Yarn, `xmlsec1`, and PostgreSQL are available through the
Ubuntu repositories and can be installed with:

```
$ sudo apt install redis nodejs postgresql yarnpkg xmlsec1
```

## Configuring `yarn`

Since Ubuntu and associated Linux distributions call `yarn` as `yarnpkg`,
it will be necessary to symlink `yarnpkg` as `yarn`:

```
$ sudo ln -s "$(which yarnpkg)" /usr/local/bin/yarn
```

## Starting Services

Despite the package being installed, systemd does not work under WSL and there
is not currently support for automatically starting services. The `redis-server`
and `postgresql` services will need to be started manually with:

```
$ sudo service redis-server start
$ sudo service postgresql start
```

## Setting PostgreSQL password

If you were not prompted to do so, it will be necessary to set the password
for the `postgres` user. This value is configured in
[config/base.ini](/config/base.ini) and by default, the expected value is
`postgres`.

The password can be set by connecting to the PostgreSQL as the `psql` user:

```
$ sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
```

*Note*: If you continue to have problems connecting to PostgreSQL, ensure that
it is running on the correct port and that there are not other PostgreSQL
servers running on other WSL installations or on the Windows host itself that
have bound to port 5432.

## Proceed with setup and running

Ensure you are using the Python 3.7.3 installed earlier by running

```
$ pyenv shell 3.7.3
```

From here, your local development environment should be sufficiently configured
to proceed with the [setup](https://github.com/dod-ccpo/atst#setup) section of
the README and to continue with running the local development server.