#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ( "$1" != "ztf" && "$1" != "lsst" ) ]]; then
    echo "Usage: $0 <ztf|lsst>" >&2
    exit 2
fi

for command in kubectl envsubst; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "This script requires '$command'." >&2
        exit 1
    fi
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
service=$1
config_file="$script_dir/config.$service"

if [[ ! -f "$config_file" ]]; then
    echo "Missing $config_file. Copy config.$service.example and configure it first." >&2
    exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    if [[ "$line" != *=* ]]; then
        echo "Invalid config line in $config_file; expected KEY=value." >&2
        exit 1
    fi

    key=${line%%=*}
    value=${line#*=}
    case "$key" in
        NAMESPACE|DOMAIN|IMAGE|REPLICAS|GITLAB_REGISTRY|GITLAB_REGISTRY_USER|GITLAB_REGISTRY_TOKEN|AE_MODEL_PATH|ANOMALY_THRESHOLD|API_TOKEN|SLACK_WEBHOOK_URL|API_ROOT_PATH|LETSENCRYPT_EMAIL) ;;
        *)
            echo "Unsupported setting '$key' in $config_file." >&2
            exit 1
            ;;
    esac
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
        value=${value:1:-1}
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value=${value:1:-1}
    fi
    printf -v "$key" '%s' "$value"
    export "$key"
done < "$config_file"

required_vars=(
    NAMESPACE DOMAIN IMAGE REPLICAS
    GITLAB_REGISTRY GITLAB_REGISTRY_USER GITLAB_REGISTRY_TOKEN
    AE_MODEL_PATH ANOMALY_THRESHOLD API_TOKEN API_ROOT_PATH
    LETSENCRYPT_EMAIL
)
for variable in "${required_vars[@]}"; do
    if [[ -z "${!variable:-}" || "${!variable}" == *'<'* ]]; then
        echo "Set a valid $variable in $config_file before deploying." >&2
        exit 1
    fi
done

if [[ ! "$REPLICAS" =~ ^[0-9]+$ ]]; then
    echo "REPLICAS in $config_file must be a non-negative integer." >&2
    exit 1
fi

if [[ "$GITLAB_REGISTRY_USER" == "SET_GITLAB_REGISTRY_USER" ||
      "$GITLAB_REGISTRY_TOKEN" == "SET_GITLAB_REGISTRY_TOKEN" ]]; then
    echo "Set GitLab registry credentials in $config_file before deploying." >&2
    exit 1
fi

if [[ "$API_TOKEN" == SET_* ]]; then
    echo "Set a strong API_TOKEN in $config_file before deploying." >&2
    exit 1
fi

if ! [[ "$ANOMALY_THRESHOLD" =~ ^([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$ ]]; then
    echo "ANOMALY_THRESHOLD in $config_file must be numeric." >&2
    exit 1
fi

kubectl apply -f <(
    NAMESPACE=$NAMESPACE \
        envsubst '${NAMESPACE}' < "$script_dir/manifests/namespace.yml"
)
kubectl apply -f <(
    LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL \
        envsubst '${LETSENCRYPT_EMAIL}' < "$script_dir/manifests/letsencrypt.yml.tpl"
)

kubectl create secret docker-registry gitlab-registry \
    --namespace "$NAMESPACE" \
    --docker-server="$GITLAB_REGISTRY" \
    --docker-username="$GITLAB_REGISTRY_USER" \
    --docker-password="$GITLAB_REGISTRY_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic "fink-api-env-$service" \
    --namespace "$NAMESPACE" \
    --from-literal=AE_MODEL_PATH="$AE_MODEL_PATH" \
    --from-literal=ANOMALY_THRESHOLD="$ANOMALY_THRESHOLD" \
    --from-literal=API_TOKEN="$API_TOKEN" \
    --from-literal=SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
    --from-literal=API_ROOT_PATH="$API_ROOT_PATH" \
    --dry-run=client -o yaml | kubectl apply -f -

template_vars='${NAMESPACE} ${SERVICE} ${DOMAIN} ${IMAGE} ${REPLICAS}'
for manifest in certificate deployment service middleware ingress; do
    NAMESPACE=$NAMESPACE SERVICE=$service DOMAIN=$DOMAIN IMAGE=$IMAGE REPLICAS=$REPLICAS \
        envsubst "$template_vars" < "$script_dir/manifests/$manifest.yml.tpl" |
        kubectl apply -f -
done

if [[ "$REPLICAS" -gt 0 ]]; then
    deployment="log-anomaly-detection-api-$service"
    kubectl rollout restart "deployment/$deployment" --namespace "$NAMESPACE"
    kubectl rollout status "deployment/$deployment" \
        --namespace "$NAMESPACE" --timeout=300s
fi
