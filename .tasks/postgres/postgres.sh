#!/usr/bin/env bash

set -euo pipefail

if [[ $# -eq 0 ]]; then
    command -v gum >/dev/null
    choice=$(gum choose "Status" "Check Updates" "Plan Upgrade" "Rehearse Upgrade" "Upgrade" "Resume Upgrade" "Configure" "Help" "Back")
    case "$choice" in
        "Status") set -- status ;;
        "Check Updates") set -- updates ;;
        "Plan Upgrade")
            update_pr=$(gum input --header 'Renovate PR number (leave blank to use the merged desired image)')
            if [[ -n "$update_pr" ]]; then
                set -- plan --pr "$update_pr"
            else
                set -- plan
            fi
            ;;
        "Upgrade")
            update_pr=$(gum input --header 'Renovate PR number (leave blank to use the merged desired image)')
            if [[ -n "$update_pr" ]]; then
                set -- upgrade --pr "$update_pr"
            else
                set -- upgrade
            fi
            ;;
        "Rehearse Upgrade" | "Resume Upgrade")
            state_dir="${OPS_POSTGRES_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/ops/postgres}"
            run_id=$(python3 - "$state_dir" <<'PY'
from pathlib import Path
import sys
for path in sorted(Path(sys.argv[1]).glob('20*T*Z-*.json'), reverse=True):
    print(path.stem)
PY
            )
            [[ -n "$run_id" ]] || { gum log --level error 'Create an upgrade plan first.'; exit 1; }
            run_id=$(printf '%s\n' "$run_id" | gum choose)
            case "$choice" in
                "Rehearse Upgrade") set -- rehearse "$run_id" ;;
                "Resume Upgrade") set -- resume "$run_id" ;;
            esac
            ;;
        "Configure")
            home_config=$(gum input --header 'Home kubeconfig' --value "${KUBECONFIG:-$ROOT_DIR/kubeconfig}")
            cloud_config=$(gum input --header 'Cloud kubeconfig')
            controller=$(gum input --header 'Preferred-home controller SSH destination')
            set -- configure --home-kubeconfig "$home_config" --cloud-kubeconfig "$cloud_config" --controller-ssh "$controller"
            ;;
        "Help") set -- --help ;;
        "Back") exec "${TASK_DIR}/ops" ;;
        *) exit 1 ;;
    esac
fi

exec python3 "${TASK_DIR}/postgres/postgres.py" "$@"
