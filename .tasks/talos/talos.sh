#!/usr/bin/env bash

CONFIG_FILE="${TALOS_DIR}/${NODE_IP}.yaml"
OPTIONS=("Apply Talos Config" "Upgrade Talos" "Upgrade Kubernetes" "Reboot Talos" "Shutdown Talos" "Reset Talos" "Generate Kubeconfig" "Rotate Client Certs" "Help" "Back")

function show_help() {
    echo "Usage: $0 [command]"
    echo "Commands:"
    echo "  apply        Apply Talos config to the node"
    echo "  upgrade      Upgrade Talos on the node"
    echo "  upgrade-k8s  Upgrade Kubernetes on the node"
    echo "  reboot       Reboot Talos on the node"
    echo "  shutdown     Shutdown the Talos node"
    echo "  reset        Reset Talos on the node"
    echo "  kubeconfig   Generate the kubeconfig for the Talos node"
    echo "Options:"
    echo "  -h, --help, help    Display this help message"
    exit 0
}

function menu() {
    choice=$(gum choose "${OPTIONS[@]}")
    if [ -n "$choice" ]; then
        echo "$choice"
    fi
}

function main() {
    local args=("$@")

    if [[ ${#args[@]} -eq 0 || "${args[0]}" == "menu" ]]; then
        args[0]=$(menu)
        if [ -z "${args[0]}" ]; then
            gum log --structured --level error "No choice selected"
            exit 1
        fi
    fi

    case "${args[0]}" in
    "Apply Talos Config" | "apply")
        check_env NODE_IP CONFIG_FILE
        check_cli op talosctl
        gum log --structured --level info "Applying Talos config to node ${NODE_IP}"
        generate_schematic
        op_signin
        if ! op inject -i "${CONFIG_FILE}" | envsubst | talosctl --nodes "${NODE_IP}" apply-config --mode auto --file /dev/stdin --config-patch "@${TALOS_DIR}/patches/patches.yaml"; then
            gum log --structured --level error "Failed to apply Talos config"
        else
            gum log --structured --level info "Successfully applied Talos config"
        fi
        ;;

    "Upgrade Talos" | "upgrade")
        check_env NODE_IP CONFIG_FILE
        check_cli talosctl yq
        gum log --structured --level info "Upgrading Talos on node ${NODE_IP}"
        generate_schematic
        if ! FACTORY_IMAGE=$(op inject -i "${CONFIG_FILE}" | envsubst | yq --exit-status '.machine.install.image'); then
            gum log --structured --level error "Failed to fetch factory image"
            exit 1
        fi
        if ! talosctl --nodes "${NODE_IP}" upgrade --image="${FACTORY_IMAGE}" --reboot-mode=powercycle --timeout=10m; then
            gum log --structured --level error "Failed to upgrade Talos"
        else
            gum log --structured --level info "Successfully upgraded Talos"
        fi
        ;;

    "Upgrade Kubernetes" | "upgrade-k8s")
        check_env NODE_IP CONFIG_FILE KUBERNETES_VERSION
        check_cli talosctl
        gum log --structured --level info "Upgrading Kubernetes on node ${NODE_IP} to version ${KUBERNETES_VERSION}"
        if ! talosctl --nodes "${NODE_IP}" upgrade-k8s --to "${KUBERNETES_VERSION}"; then
            gum log --structured --level error "Failed to upgrade Kubernetes"
        else
            gum log --structured --level info "Successfully upgraded Kubernetes"
        fi
        ;;

    "Reboot Talos" | "reboot")
        check_env NODE_IP
        check_cli talosctl
        gum log --structured --level info "Rebooting Talos on node ${NODE_IP}"
        if ! talosctl --nodes "${NODE_IP}" reboot --mode=powercycle; then
            gum log --structured --level error "Failed to reboot Talos"
        else
            gum log --structured --level info "Successfully rebooted Talos"
        fi
        ;;

    "Shutdown Talos" | "shutdown")
        check_env NODE_IP
        check_cli talosctl
        if gum confirm "Shutdown the Talos node ${NODE_IP} ... continue?"; then
            gum log --structured --level info "Shutting down Talos on node ${NODE_IP}"
            if ! talosctl shutdown --nodes "${NODE_IP}" --force; then
                gum log --structured --level error "Failed to shutdown Talos"
            else
                gum log --structured --level info "Successfully shut down Talos"
            fi
        else
            gum log --structured --level info "Shutdown cancelled"
        fi
        ;;

    "Reset Talos" | "reset")
        check_env NODE_IP
        check_cli talosctl
        if gum confirm "Reset Talos node ${NODE_IP} ... continue?"; then
            gum log --structured --level info "Resetting Talos on node ${NODE_IP}"
            if ! talosctl reset --nodes "${NODE_IP}" --graceful=false; then
                gum log --structured --level error "Failed to reset Talos"
            else
                gum log --structured --level info "Successfully reset Talos"
            fi
        else
            gum log --structured --level info "Reset cancelled"
        fi
        ;;

    "Generate Kubeconfig" | "kubeconfig")
        check_env NODE_IP ROOT_DIR
        check_cli talosctl
        gum log --structured --level info "Generating kubeconfig for node ${NODE_IP}"
        if ! talosctl kubeconfig --nodes "${NODE_IP}" --force --force-context-name main "${ROOT_DIR}"; then
            gum log --structured --level error "Failed to generate kubeconfig"
        else
            gum log --structured --level info "Successfully generated kubeconfig"
        fi
        ;;

    "Rotate Client Certs" | "rotate-certs")
        check_env NODE_IP CONFIG_FILE
        check_cli op yq talosctl base64 gum

        gum log --structured --level info "Rotating client cert"
        op_signin

        local injected
        injected=$(mktemp)
        op inject -i "${CONFIG_FILE}" | envsubst >"${injected}"

        local ca_crt_b64
        local ca_key_b64
        ca_crt_b64=$(yq -r '.machine.ca.crt' "${injected}" | tr -d '\n')
        ca_key_b64=$(yq -r '.machine.ca.key' "${injected}" | tr -d '\n')

        local tmp
        tmp=$(mktemp -d)
        trap 'rm -rf "${tmp}"' EXIT
        echo "${ca_crt_b64}" | base64 -d >"${tmp}/ca.crt"
        echo "${ca_key_b64}" | base64 -d >"${tmp}/ca.key"

        pushd "${tmp}" >/dev/null || return 1
        talosctl gen key --name admin                         # admin.key
        talosctl gen csr --key admin.key --ip 127.0.0.1       # admin.csr
        talosctl gen crt --ca ca --csr admin.csr --name admin # admin.crt
        popd >/dev/null || return 1

        yq -i '
          .contexts.main.crt = "'"$(base64 -w0 "${tmp}/admin.crt")"'" |
          .contexts.main.key = "'"$(base64 -w0 "${tmp}/admin.key")"'"
        ' talosconfig

        gum log --structured --level info "Rotation complete – talosconfig updated"
        ;;

    "-h" | "--help" | "Help")
        show_help
        ;;

    "Back")
        ops
        ;;

    *)
        gum log --structured --level error "Unknown command" "command" "${args[0]}"
        show_help
        ;;
    esac
}

main "$@"
