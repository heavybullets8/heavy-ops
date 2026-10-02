#!/usr/bin/env bash
set -euo pipefail

readonly DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly NAMESPACE=mkjm-hosting-trial
readonly CONTEXT=main
readonly API_SERVER=https://192.168.200.16:6443

usage() {
  cat >&2 <<'EOF'
Set TRIAL_KUBECONFIG to an explicit kubeconfig for the home cluster.
Usage:
  trial.sh start IMAGE@sha256:DIGEST [--pull-secret-file DOCKER_CONFIG_JSON]
  trial.sh status
  trial.sh access mk|jm [LOCAL_PORT]
  trial.sh teardown destroy-mkjm-hosting-trial
EOF
  exit 2
}

[[ $# -ge 1 ]] || usage
action=$1
shift
[[ -n "${TRIAL_KUBECONFIG:-}" && -f "$TRIAL_KUBECONFIG" ]] || {
  echo 'TRIAL_KUBECONFIG must name an existing kubeconfig file.' >&2
  exit 2
}

kubectl_trial() {
  kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context "$CONTEXT" "$@"
}

actual_server=$(kubectl_trial config view --minify -o jsonpath='{.clusters[0].cluster.server}')
[[ "$actual_server" == "$API_SERVER" ]] || {
  echo "Refusing context $CONTEXT: API server is $actual_server, expected $API_SERVER." >&2
  exit 2
}

case "$action" in
  start)
    [[ $# -eq 1 || ($# -eq 3 && "$2" == --pull-secret-file) ]] || usage
    image=$1
    [[ "$image" =~ ^[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}$ ]] || {
      echo 'IMAGE must be an immutable registry reference ending in @sha256:<64 lowercase hex>.' >&2
      exit 2
    }
    pull_secret='[]'
    if [[ $# -eq 3 ]]; then
      [[ -r "$3" ]] || {
        echo 'Pull secret file must be readable.' >&2
        exit 2
      }
      pull_secret='[{name: trial-registry}]'
    fi
    existing=$(kubectl_trial get namespace "$NAMESPACE" --ignore-not-found -o name)
    [[ -z "$existing" ]] || {
      echo "Namespace $NAMESPACE already exists. Use status, or tear it down explicitly before a fresh run." >&2
      exit 2
    }
    kubectl_trial apply -f "$DIR/namespace.yaml"
    kubectl_trial apply -f "$DIR/network.yaml"

    secret_dir=$(mktemp -d)
    chmod 700 "$secret_dir"
    trap 'rm -rf -- "$secret_dir"' EXIT
    password=$(openssl rand -hex 32)
    printf %s "$password" > "$secret_dir/POSTGRES_PASSWORD"
    printf 'postgresql://mkjm_trial:%s@postgres.mkjm-hosting-trial.svc.cluster.local:5432/mkjm_hosting_trial' "$password" > "$secret_dir/DATABASE_URL"
    unset password
    kubectl_trial -n "$NAMESPACE" create secret generic trial-db \
      --from-file="POSTGRES_PASSWORD=$secret_dir/POSTGRES_PASSWORD" \
      --from-file="DATABASE_URL=$secret_dir/DATABASE_URL" \
      --dry-run=client -o yaml | kubectl_trial apply -f -
    rm -rf -- "$secret_dir"
    trap - EXIT

    if [[ $# -eq 3 ]]; then
      kubectl_trial -n "$NAMESPACE" create secret generic trial-registry \
        --type=kubernetes.io/dockerconfigjson \
        --from-file=".dockerconfigjson=$3" \
        --dry-run=client -o yaml | kubectl_trial apply -f -
    fi

    kubectl_trial apply -f "$DIR/postgres.yaml"
    kubectl_trial -n "$NAMESPACE" rollout status deployment/postgres --timeout=5m
    sed -e "s|__TRIAL_IMAGE__|$image|g" -e "s|__TRIAL_PULL_SECRET__|$pull_secret|g" "$DIR/apps.yaml.in" | kubectl_trial apply -f -
    kubectl_trial -n "$NAMESPACE" rollout status deployment/mk --timeout=5m
    kubectl_trial -n "$NAMESPACE" rollout status deployment/jm --timeout=5m
    ;;
  status)
    [[ $# -eq 0 ]] || usage
    kubectl_trial -n "$NAMESPACE" get deployments,pods,services,pvc,networkpolicies -o wide
    ;;
  access)
    [[ $# -ge 1 && $# -le 2 ]] || usage
    site=$1
    [[ "$site" == mk || "$site" == jm ]] || usage
    port=${2:-18080}
    [[ "$port" =~ ^[0-9]{2,5}$ && "$port" -ge 1024 && "$port" -le 65535 ]] || usage
    kubectl_trial -n "$NAMESPACE" port-forward --address 127.0.0.1 "service/$site" "$port:8000"
    ;;
  teardown)
    [[ $# -eq 1 && "$1" == destroy-mkjm-hosting-trial ]] || usage
    label=$(kubectl_trial get namespace "$NAMESPACE" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/part-of}')
    [[ "$label" == "$NAMESPACE" ]] || {
      echo "Refusing to delete namespace $NAMESPACE: trial ownership label missing." >&2
      exit 2
    }
    kubectl_trial delete namespace "$NAMESPACE" --wait=true --timeout=5m
    ;;
  *) usage ;;
esac
