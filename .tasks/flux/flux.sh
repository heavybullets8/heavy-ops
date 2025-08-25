#!/usr/bin/env bash

OPTIONS=("Reconcile All" "Help" "Back")

: "${MAX_PARALLEL:=8}"
: "${FLUX_TIMEOUT:=30s}"

function show_help() {
    echo "Usage: $0 [command]"
    echo "Commands:"
    echo "  r, reconcile    Reconcile all Kustomizations and HelmReleases in parallel"
    echo "Options:"
    echo "  -h, --help, help    Display this help message"
    exit 0
}

function menu() {
    choice=$(gum choose "${OPTIONS[@]}")
    [ -n "$choice" ] && echo "$choice"
}

function throttle() {
    while true; do
        running=$(jobs -pr | wc -l | tr -d ' ')
        ((running < MAX_PARALLEL)) && break
        sleep 0.2
    done
}

function reconcile_kustomization() {
    local ns="$1" name="$2"
    echo "[INFO] Reconciling Kustomization namespace=${ns} name=${name}"
    if flux reconcile kustomization -n "$ns" "$name" --timeout "$FLUX_TIMEOUT" >/dev/null 2>&1; then
        echo "[INFO] Kustomization OK namespace=${ns} name=${name}"
    else
        echo "[ERROR] Kustomization FAILED namespace=${ns} name=${name}"
    fi
}

function reconcile_helmrelease() {
    local ns="$1" name="$2"
    echo "[INFO] Reconciling HelmRelease namespace=${ns} name=${name}"
    if flux reconcile helmrelease -n "$ns" "$name" --timeout "$FLUX_TIMEOUT" >/dev/null 2>&1; then
        echo "[INFO] HelmRelease OK namespace=${ns} name=${name}"
        return
    fi
    echo "[WARN] HelmRelease initial reconcile failed; retrying with --with-source --reset --force namespace=${ns} name=${name}"
    if flux reconcile helmrelease -n "$ns" "$name" --with-source --reset --force --timeout "$FLUX_TIMEOUT" >/dev/null 2>&1; then
        echo "[INFO] HelmRelease RECOVERED namespace=${ns} name=${name}"
    else
        echo "[ERROR] HelmRelease FAILED (after forced retry) namespace=${ns} name=${name}"
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
    "Reconcile All" | "r" | "reconcile")
        gum log --structured --level debug "Fetching kustomizations"
        if ! kustomizations=$(kubectl get kustomization --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}'); then
            gum log --structured --level error "Failed to fetch kustomizations"
            exit 1
        fi

        gum log --structured --level debug "Fetching helm releases"
        if ! helmreleases=$(kubectl get helmrelease --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}'); then
            gum log --structured --level error "Failed to fetch helm releases"
            exit 1
        fi

        while IFS=$'\t' read -r ns name; do
            [ -z "$ns" ] && continue
            throttle
            reconcile_kustomization "$ns" "$name" &
        done <<<"$kustomizations"

        while IFS=$'\t' read -r ns name; do
            [ -z "$ns" ] && continue
            throttle
            reconcile_helmrelease "$ns" "$name" &
        done <<<"$helmreleases"

        wait
        gum log --structured --level info "All reconcile jobs finished"
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
