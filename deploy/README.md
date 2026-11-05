# k3s Deployment

This directory deploys the ZTF and LSST log anomaly detection inference APIs to a single-node (server/vm) k3s cluster. Each API has its own local configuration file, while Kubernetes manifests are split by the selected API.

## Repository organisation

- `config.ztf` and `config.lsst`: local settings for the application,
  Kubernetes resources, container image, GitLab registry credentials, and
  Let's Encrypt contact email. These files are ignored by Git.
- `manifests/namespace.yml`: application namespace.
- `manifests/letsencrypt.yml.tpl`: Let's Encrypt production ClusterIssuer.
- `manifests/certificate.yml.tpl`: shared TLS certificate.
- `manifests/deployment.yml.tpl`: API Deployment.
- `manifests/service.yml.tpl`: internal ClusterIP Service.
- `manifests/middleware.yml.tpl`: Traefik path-prefix middleware.
- `manifests/ingress.yml.tpl`: HTTPS Ingress.
- `init-cluster.sh`: installs and configures a single-node k3s server on
  almalinux9X vm/systems.
- `setup-tls.sh`: installs cert-manager in the cluster.
- `apply.sh`: creates Kubernetes Secrets and deploys one selected API.

## Install the k3s server (only once after VM creation)

Run this on the  server that will host k3s:

```bash
./deploy/init-cluster.sh
```

Load the persistent kubeconfig setting in the current shell:

```bash
source ~/.bashrc
kubectl get nodes
```

The kubeconfig created by this script is for local administration on the k3s
server.

## Create and edit the API configuration files

From the repository root, create the local configuration files:

```bash
cp deploy/config.ztf.example deploy/config.ztf
cp deploy/config.lsst.example deploy/config.lsst
```

Edit `deploy/config.ztf` and `deploy/config.lsst` directly. Each file contains
the application settings (`AE_MODEL_PATH`, `ANOMALY_THRESHOLD`, `API_TOKEN` -- we can generate one with : `import secrets; print(secrets.token_hex(32))` -- ,
`SLACK_WEBHOOK_URL`, and `API_ROOT_PATH`), Kubernetes settings (namespace,
domain, and replica count), GitLab image and registry settings
(`IMAGE`, `GITLAB_REGISTRY`, `GITLAB_REGISTRY_USER`, and
`GITLAB_REGISTRY_TOKEN`), and the Let's Encrypt contact email.


Note : The LSST model and its threshold are not available yet. Keep
`REPLICAS='0'` and we not deploy LSST until its model is present.

## Install cert-manager (only once)

After k3s is ready, install cert-manager once:

```bash
./deploy/setup-tls.sh
```

This uses cert-manager `v1.18.2` by default. To use another release:

```bash
./deploy/setup-tls.sh v1.18.3
```

The Let's Encrypt production ClusterIssuer is applied by `apply.sh`.

## Deploy the APIs (to be applied every when the image is updated)

Deploy ZTF:

```bash
./deploy/apply.sh ztf
```

**Note**: When the LSST model and threshold are ready, set `REPLICAS='1'` in
`deploy/config.lsst` and deploy LSST:

```bash
./deploy/apply.sh lsst
```

The public endpoints for client (with the right TOKEN_API) are:

- ZTF: `https://<DOMAIN>/ztf/predict`
- LSST: `https://<DOMAIN>/lsst/predict`

Clients (nginx-logs-exporters) must send the raw 5min logs with the configured
`API_TOKEN` in the `X-API-Token` header.

Run `./deploy/apply.sh ztf` or `./deploy/apply.sh lsst` again after changing the
corresponding configuration to update its Kubernetes Secrets and resources.