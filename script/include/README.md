# scriptz

These script fragments are shared between all of the ATAT applications, powering
their /script files. See 
[Scripts to Rule Them All](https://github.com/github/scripts-to-rule-them-all) 
and an ATAT application repository for details.

- `global_header.inc.sh`: Run by all /script files at the start of the script.
- `helper_functions.inc.sh`: Contains general helper functions; sourced by 
global_header.inc.sh
- `run_setup`: Main logic run by most /script/setup scripts, after they set any
relevant environment variables. Initializes the local environment to run the app.
- `run_bootstrap`: Main logic run by most /script/bootstrap scripts, after they set 
any relevant environment variables. Installs application dependencies.
- `run_test`: Main logic run by most /script/test scripts, after they set any
relevant environment variables. Executes lint, static analysis, and unit tests.
- `run_update`: Main logic run by most /script/update scripts, after they set any
 relevant environment variables. Executes application dependency updates, and
 potentially DB migrations.
- `run_dev_server`: Main logic run by most /script/dev_server scripts, after any
 relevant environment variables are set. Launches an application server in DEBUG
 mode in the background.
- `run_alpine_setup`: Main logic run by most /script/alpine_setup scripts, after 
they set any relevant environment variables. Adds Alpine Linux specific system 
dependencies required to run the app (used by Docker builds).
- `setup_functions.inc.sh`: Sourced by run_setup; contains setup specific 
functions.
- `bootstrap_functions.inc.sh`: Sourced by run_bootstrap; contains bootstrap 
specific functions.
- `test_functions.inc.sh`: Sourced by run_test; contains test specific 
functions.
- `update_functions.inc.sh`: Sourced by run_update; contains update specific
 functions.
- `dev_server_functions.inc.sh`: Sourced by run_dev_server; contains dev_server
 specific functions.
- `alpine_setup_functions.inc.sh`: Sourced by run_alpine_setup; contains 
alpine_setup specific functions.

## Requirements

- **[Python 3.8](https://www.python.org/downloads/)**
- **[poetry](https://python-poetry.org/docs/)**

**Note:** None of these script fragments are designed to be run by themselves. 
They should be sourced by the relevant bash script in an application's /script 
directory.

#### Ubuntu 18.04 Instructions

Install pip:
```
sudo apt install python3-distutils
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py --user
```

Install poetry:
```
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
```
