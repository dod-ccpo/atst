# Ghost Inspector Readme

The suite of Ghost Inspector tests that runs as part of the CI workflow
can be found [here](https://app.ghostinspector.com/suites/5d9e3d303ab5d56633c11598). Its current status is https://api.ghostinspector.com/v1/suites/5d9e3d303ab5d56633c11598/status-badge

[Another suite](https://app.ghostinspector.com/suites/5d9603f1af31210914da04ca) of Ghost Inspector tests runs once daily against the Staging site. Status: https://api.ghostinspector.com/v1/suites/5d9603f1af31210914da04ca/status-badge

## Testing philosophy

The tests have been created to traverse the most common user flows in ATAT. There are a few tests (e.g. "New Portfolio - no optional fields")
that check for regressions. Others (e.g. "Remove Portfolio Member") check less-common, "negative path" flows. Tests are added as necessary
to ensure fairly thorough checking of ATAT.

The tests are constructed in a "stepwise" fashion; that is, no individual test depends upon another, and each test checks one step in complex
user flows. As an example, there are six tests for creating a new Task Order, one corresponding to each screen in the process plus one
for adding a second CLIN to a TO. Each test relies on Ghost Inspector's "Import steps from Test X" functionality to perform all the
necessary setup before running its own check. This also ensures that tests can be run in any sequence since Ghost Inspector launches up to
four tests simultaneously.

## Handling UI changes

As with any UI-testing system, Ghost Inspector tests will fail because of changes to the UI. This can be problematic since failures
cause errors in the CI workflow, which could cause the Pull Request not to be deployed. To mitigate this issue, we have utilized
the following strategies:

1. Front-end developers notify the project QA lead of changes that will potentially cause Ghost Inspector failures --OR-- the
QA lead monitors all failures on the CI suite and determines that such a change has occurred.

2. If only one step in a test is affected (e.g. a visual but not functional change), that step can be marked as "optional" in
the Ghost Inspector UI.

3. If the (potentially) failing test will need to be reworked to account for functional changes, the test is moved from the CI
suite to the "Holding" suite until the PR is merged. Then the test can be edited and returned to the CI suite.

## Running Ghost Inspector tests locally

To run the Ghost Inspector tests against a local instance of ATAT,
you will need the following:

- [docker](https://docs.docker.com/v17.12/install/)
- the prerequisite variable information listed [here](https://ghostinspector.com/docs/integration/circle-ci/):
 - NGROK_TOKEN - Either a personal token or a team shared one.
 - GI_API_KEY - Shared Ghost inspector token, listed in team password manager
 - GI_SUITE - The suite ID of the GI suite you wish to run, which can be obtained from the GI dashboard.


First you will need to build a copy of the container:

```
docker build . --build-arg IMAGE=<location of the base image from a container repository> --build-arg CSP=azure -f ./Dockerfile -t atat:builder --target builder
```

This builds the first stage of the docker container, which is the one we need to run integration tests. You can tag the container whatever you want; in the example we've tagged it "atat:builder".

Then you can run the integration tests script. You will need four environment variables set: the three mentioned previously and CONTAINER_IMAGE. You can either export them or set them inline in the command you use to run the script. In the example we'll set them inline:

```
NGROK_TOKEN=<token> GI_API_KEY=<api key> GI_SUITE=<suite> CONTAINER_IMAGE=atat:builder ./script/integration_tests
```

Alternatively, if you need to run the tests against a secured server with a static url, you can use this command. NOTE: this **requires** you to use an ngrok token associated with a paid ngrok account, since reserved domains are only available there.

```
NGROK_TOKEN=<token> GI_API_KEY=<api key> GI_SUITE=<suite> NGROK_DOMAIN=<reserved_domain> CONTAINER_IMAGE=atat:builder ./script/integration_tests_secure
```

The results of the test are visible on the GI website in the suite you chose to run.

### Troubleshooting

- If you get errors regarding ports being in use, make sure you don't have instances of the Flask app, Postgres, or Redis running locally using those ports.
- If the curl command used to wait for the application container times out and fails, you can increase the timeout by setting a CONTAINER_TIMEOUT environment variable. It defaults to 200 in the script.
- You may see errors like "No such container". The script attempts to clean up any previous incarnations of the containers before it starts, and it may print errors when it doesn't find them. This is fine.
- The script is, for the most part, a series of docker commands, so try running the commands individually and debugging that way.
