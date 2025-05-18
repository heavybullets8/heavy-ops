#!/usr/bin/env bash

CONFIG_FILE="${TALOS_DIR}/${NODE_IP}.yaml.j2"
OPTIONS=("Apply Talos Config" "Upgrade Talos" "Upgrade Kubernetes" "Reboot Talos" "Shutdown Talos" "Reset Talos" "Generate Kubeconfig" "Help" "Back")

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
        check_cli minijinja-cli op talosctl
        gum log --structured --level info "Applying Talos config to node ${NODE_IP}"
        op_signin
        if ! minijinja-cli "${CONFIG_FILE}" | op inject | talosctl --nodes "${NODE_IP}" apply-config --mode auto --file /dev/stdin; then
            gum log --structured --level error "Failed to apply Talos config"
        else
            gum log --structured --level info "Successfully applied Talos config"
        fi
        ;;

    "Upgrade Talos" | "upgrade")
        check_env NODE_IP CONFIG_FILE
        check_cli minijinja-cli talosctl yq
        gum log --structured --level info "Upgrading Talos on node ${NODE_IP}"
        if ! FACTORY_IMAGE=$(minijinja-cli "${CONFIG_FILE}" | yq --exit-status 'select(document_index == 0) | .machine.install.image'); then
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
