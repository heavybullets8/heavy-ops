#!/usr/bin/env bash

function apply_talos_config() {
    local config_file="${TALOS_DIR}/${NODE_IP}.yaml.j2"
    local machine_config
    gum log --structured --level info "Applying Talos configuration"
    machine_config=$(render_template "$config_file")
    gum log --structured --level info "Talos config rendered successfully"
    local output
    if ! output=$(echo "$machine_config" | talosctl --nodes "$NODE_IP" apply-config --insecure --file /dev/stdin --config-patch "@${TALOS_DIR}/patches/enp130s0f0np0.yaml" --config-patch "@${TALOS_DIR}/patches/enp130s0f1np1.yaml" 2>&1); then
        if [[ "$output" == *"certificate required"* ]]; then
            gum log --structured --level warn "Talos already has an applied configuration..."
        else
            gum log --structured --level error "Failed to apply Talos config" "output" "$output"
            exit 1
        fi
    else
        gum log --structured --level info "Talos config applied successfully"
    fi
}

function bootstrap_talos() {
    local output
    gum log --structured --level info "Bootstrapping Talos"
    until output=$(talosctl --nodes "$NODE_IP" bootstrap 2>&1 || true) && [[ "${output}" == *"AlreadyExists"* ]]; do
        gum log --structured --level info "Talos bootstrap in progress, waiting 10 seconds..."
        sleep 10
    done
    gum log --structured --level info "Talos is bootstrapped"
}

function wait_for_nodes() {
    gum log --structured --level info "Waiting for node to be available"
    if kubectl wait nodes --for=condition=Ready=True --all --timeout=10s &>/dev/null; then
        gum log --structured --level info "Node is ready, skipping wait"
        return
    fi
    # HACK: hmmm
    until kubectl wait nodes --for=condition=Ready=False --all --timeout=10s &>/dev/null; do
        gum log --structured --level info "Node not ready, retrying in 10s"
        sleep 10
    done
}

function apply_resources() {
    local resources_file="${BOOTSTRAP_DIR}/resources.yaml.j2"
    gum log --structured --level info "Applying resources"
    if [[ ! -f "$resources_file" ]]; then
        gum log --structured --level error "Resources file not found" "file" "$resources_file"
        exit 1
    fi
    local output
    output=$(render_template "$resources_file")
    if echo "$output" | kubectl diff --filename - &>/dev/null; then
        gum log --structured --level warn "Resources are up-to-date"
        return 0
    fi
    if echo "$output" | kubectl apply --server-side --filename - &>/dev/null; then
        gum log --structured --level info "Resources applied"
    else
        gum log --structured --level error "Failed to apply resources"
        exit 1
    fi
}

function apply_crds() {
    gum log --structured --level info "Applying CRDs"
    local -r crds=(
        # renovate: datasource=github-releases depName=kubernetes-sigs/gateway-api
        https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.3.0/experimental-install.yaml
        # renovate: datasource=github-releases depName=prometheus-operator/prometheus-operator
        https://github.com/prometheus-operator/prometheus-operator/releases/download/v0.84.1/stripped-down-crds.yaml
        # renovate: datasource=github-releases depName=kubernetes-sigs/external-dns
        https://raw.githubusercontent.com/kubernetes-sigs/external-dns/refs/tags/v0.18.0/config/crd/standard/dnsendpoints.externaldns.k8s.io.yaml
    )
    for crd in "${crds[@]}"; do
        if kubectl diff --filename "${crd}" &>/dev/null; then
            gum log --structured --level info "CRDs are up-to-date" "crd" "$crd"
            continue
        fi
        if kubectl apply --server-side --filename "${crd}" &>/dev/null; then
            gum log --structured --level info "CRDs applied" "crd" "$crd"
        else
            gum log --structured --level error "Failed to apply CRD" "crd" "$crd"
        fi
    done
}

function apply_helm_releases() {
    local helmfile_file="${BOOTSTRAP_DIR}/helmfile.yaml"
    gum log --structured --level info "Applying Helm releases"
    if [[ ! -f "$helmfile_file" ]]; then
        gum log --structured --level error "Helmfile not found" "file" "$helmfile_file"
        exit 1
    fi
    if ! helmfile --file "$helmfile_file" apply --hide-notes --skip-diff-on-install --suppress-diff --suppress-secrets; then
        gum log --structured --level error "Failed to apply Helm releases"
        exit 1
    fi
    gum log --structured --level info "Helm releases applied successfully"
}

function main() {
    check_env KUBECONFIG KUBERNETES_VERSION TALOS_VERSION NODE_IP
    check_cli helmfile jq kubectl kustomize minijinja-cli op talosctl yq
    gum confirm "Bootstrap the Talos node ${NODE_IP} ... continue?" || exit 0
    op_signin
    apply_talos_config
    bootstrap_talos
    fetch_kubeconfig
    wait_for_nodes
    apply_resources
    apply_crds
    apply_helm_releases
    gum log --structured --level info "Cluster bootstrapped successfully!"
}

main
