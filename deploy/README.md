# Kubernetes Deployment Configuration

This folder contains Kubernetes deployment configuration for Azure. The following assumes that you have `kubectl` installed and configured with permissions to a Kubernetes cluster.

## Applying K8s configuration

Applying the K8s config relies on a combination of kustomize and envsubst. Kustomize comes packaged with kubectl v0.14 and higher. envsubst is part of the gettext package. It can be installed with `brew install gettext` for MacOS users.

The production configuration (master.atat.dev, currently) is reflected in the configuration found in the `deploy/azure/overlays/cloudzero-pwdev-master` directory. Configuration relies on kustomize to overwrite the base config with values appropriate for that environment. You can find more information about using kustomize [here](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/). Kustomize does not manage templating, and certain values need to be templated. These include:

- CONTAINER_IMAGE: The ATAT container image to use.
- NGINX_CONTAINER_IMAGE: Container image to run the nginx server.
- MAIN_DOMAIN: The host domain for the environment.
- TENANT_ID: The id of the active directory tenant in which the cluster and it's associated users exist. This is a GUID.
- VMSS_CLIENT_ID: The client ID for the managed identity associated with the VMSS underlying the AKS instance. This managed identity should have read access to the Key Vault specified by KV_NAME.
- KV_NAME: The name of the Key Vault where ATAT's configuration secrets are stored.

These values must be set in your environment. We use envsubst to substitute values for these variables. There is a wrapper script (script/k8s_config) that will output the compiled configuration, using a combination of kustomize and envsubst.

To apply config, you should first do a diff to determine whether your new config introduces unexpected changes. These examples assume that all the relevant environment variables listed above have been set:

```
./script/k8s_config deploy/azure/overlays/cloudzero-pwdev-master | kubectl diff -f -
```

Here, `kubectl kustomize` assembles the config and streams it to STDOUT. We specify environment variables for envsubst to use and pass the names of those env vars as a string argument to envsubst. This is important, because envsubst will override NGINX variables in the NGINX config if you don't limit its scope. Finally, we pipe the result from envsubst to `kubectl diff`, which reports a list of differences. Note that some values tracked by K8s internally might have changed, such as [`generation`](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.16/#objectmeta-v1-meta). This is fine and expected.

If you are satisfied with the output from the diff, you can apply the new config the same way:

```
./script/k8s_config deploy/azure/overlays/cloudzero-pwdev-master | kubectl apply -f -
```

**Note:** Depending on how your `kubectl` config is set up, these commands may need to be adjusted. If you have configuration for multiple clusters, you may need to specify the `kubectl` context for each command with the `--context` flag (something like `kubectl --context=my-cluster [etc.]` or `kubectl --context=azure [etc.]`).

## SSL/TLS

### Renewing TLS certs

For details on how to renew our TLS certificates for the `*.atat.dev` development sites, check [the project wiki](https://ccpo.atlassian.net/wiki/spaces/AT/pages/426934409/Renewing+TLS+Certificates+for+.atat.dev+sites)

### Create the Key Vault certificate object

Once you have obtained the certs, you can create or update the Key Vault certificate object:

```
az keyvault certificate import --vault-name my-vault-name --name my-cert-object-name --file /path/to/my/all.pem
```

Make sure that the vault name and cert name match the ones used in the FlexVol integration, discussed in "Secrets Management" below.

Once the keyvault entry is updated you will need to restart deployment with these new certs:

`kubectl -n master rollout restart deployment atat`

That's the end of the process of renewing certs using certbot and Let's Encrypt. If everything went well then you should be able to load your site and see the new certificate on it.

### Create the Diffie-Hellman parameters

Diffie-Hellman parameters allow per-session encryption of SSL traffic to help improve security. We currently store our parameters in KeyVault, the value can be updated using the following command. Note: Generating the new paramter can take over 10 minutes and there won't be any output while it's running.
```
az keyvault secret set --vault-name <VAULT NAME> --name <NAME OF PARAM> --value "$(openssl genpkey -genparam -algorithm DH -outform pem -pkeyopt dh_paramgen_prime_len:4096 2> /dev/null)"
```
---

# Secrets Management

Secrets, keys, and certificates are managed from Azure Key Vault. These items are mounted into the containers at runtime using the FlexVol implementation described below.

The following are mounted into the NGINX container in the atat pod:

- The TLS certs for the site
- The DH parameter for TLS connections

These are mounted into every instance of the Flask application container (the atat container, the celery worker, etc.):

- The Azure storage key used to access blob storage (AZURE_STORAGE_KEY)
- The password for the SMTP server used to send mail (MAIL_PASSWORD)
- The Postgres database user password (PGPASSWORD)
- The Redis user password (REDIS_PASSWORD)
- The Flask secret key used for session signing and generating CSRF tokens (SECRET_KEY)

Secrets should be added to Key Vault with the following naming pattern: [branch/environment]-[all-caps config setting name]. Note that Key Vault does not support underscores. Substitute hyphens. For example, the config setting for the SMTP server password is MAIL_SERVER. The corresponding secret name in Key Vault is "master-MAIL-SERVER" for the credential used in the primary environment.These secrets are mounted into the containers via FlexVol.

To add or manage secrets, keys, and certificates in Key Vault, see the [documentation](https://docs.microsoft.com/en-us/azure/key-vault/quick-create-cli).

# Setting Up FlexVol for Secrets

## Preparing Azure Environment

A Key Vault will need to be created. Save its full id (the full path) for use later.

## Preparing Cluster

The 2 following k8s configs will need to be applied to the cluster. They do not need to be namespaced, the latter will create a `kv` namespace for itself.
```
kubectl apply -f deploy/azure/storage-class.yaml
kubectl apply -f deploy/azure/keyvault/kv-flex-vol-installer.yaml
```

## Using the FlexVol

There are 3 steps to using the FlexVol to access secrets from KeyVault

1. For the resource in which you would like to mount a FlexVol, add a metadata label with the selector from `aadpodidentity.yml`
    ```
    metadata:
      labels:
        app: atat
        role: web
        aadpodidbinding: atat-kv-id-binding
    ```

2. Register the FlexVol as a mount and specifiy which secrets you want to mount, along with the file name they should have. The `keyvaultobjectnames`, `keyvaultobjectaliases`, and `keyvaultobjecttypes` correspond to one another, positionally. They are passed as semicolon delimited strings, examples below.

    ```
    - name: volume-of-secrets
      flexVolume:
        driver: "azure/kv"
        options:
          usepodidentity: "true"
          keyvaultname: "<NAME OF KEY VAULT>"
          keyvaultobjectnames: "mysecret;mykey;mycert"
          keyvaultobjectaliases: "mysecret.pem;mykey.txt;mycert.crt"
          keyvaultobjecttypes: "secret;key;cert"
          tenantid: $TENANT_ID
    ```

3. Tell the resource where to mount your new volume, using the same name that you specified for the volume above.
    ```
    - name: nginx-secret
      mountPath: "/usr/secrets/"
      readOnly: true
    ```

4. Once applied, the directory specified in the `mountPath` argument will contain the files you specified in the flexVolume. In our case, you would be able to do this:
    ```
    $ kubectl exec -it CONTAINER_NAME -c atat ls /usr/secrets
    mycert.crt
    mykey.txt
    mysecret.pem
    ```

# NGINX Container

We use a special Red Hat Linux container provided by the DOD Iron Bank repository.
This image runs the NGINX server as a non-root user that is part of a group with an explicit GID.
Both of these qualities are considered best practice for Docker images.

> Iron Bank is the DoD repository of digitally signed, binary container images that have been hardened according to the Container Hardening Guide coming from Iron Bank. Containers accredited in Iron Bank have DoD-wide reciprocity across classifications.

> Avoid installing or using sudo as it has unpredictable TTY and signal-forwarding behavior that can cause problems.

> Users and groups in an image are assigned a non-deterministic UID/GID in that the “next” UID/GID is assigned regardless of image rebuilds. So, if it’s critical, you should assign an explicit UID/GID.

https://software.af.mil/dsop/services/

https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user

## Building

The `- < Dockerfile` pattern omits the build context, which isn't necessary for
the nginx server

```
docker build -t nginx:rhel-8.2 - < nginx.Dockerfile --build-arg IMAGE=<base-image-tag>
```

After verifying that your docker container is working (by accessing the server
locally) you can tag and push the image to our repositoy. Your image tag should
follow the example set here.

```
docker tag nginx:rhel-8.2 <nginx-image-tag>
az acr login -n <cloud-zero-registry-name>
docker push <nginx-image-tag>
```

Now you should take the time to set your `NGINX_CONTAINER_IMAGE` environment
variable to whatever you chose for your `nginx-image-tag` value.

## Deployment

Preview the configuration changes with this command. Make sure the only change
is to the nginx image and the generation number. If more changes exist, then
you need to rebase onto staging.

```
source .env.cloudzero-pwdev-staging && script/k8s_config deploy/overlays/cloudzero-pwdev-staging/ | kubectl -n staging diff -f -
```

After you've verfied your changes, you can apply!

```
source .env.cloudzero-pwdev-staging && script/k8s_config deploy/overlays/cloudzero-pwdev-staging/ | kubectl -n staging apply -f -
```

Preview the deployment status of your containers with the pods command.

```
kubectl -n staging get pods
```

And check that it's actually using your updated config.

```
kubectl -n staging describe pod <pod-id>
```

# Miscellaneous Notes

- The uWSGI config file in deploy/azure/uwsgi.ini is symlinked from that location to the repo root. It serves as a configuration reference and can be used for tests of the Docker build. The primary copy needs to reside in the same location as the kustomization.yml file because kustomize will not load files that are symlinks or live in parent directories for security reasons.
