#!/usr/bin/env bash
set -euo pipefail
umask 077
task_root=$(cd "$(dirname "$0")/../.." && pwd)
rotation_source=${1:-$task_root/talos/talos.sh}
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
export ROOT_DIR="$fixture" TALOS_DIR="$fixture" NODE_IP=127.0.0.1 TALOSCONFIG="$fixture/talosconfig"
export TMPDIR="$fixture/tmp"
mkdir "$TMPDIR" "$fixture/bin"
openssl req -x509 -newkey ed25519 -keyout "$fixture/ca.key" -out "$fixture/ca.crt" -noenc -days 730 -subj /CN=test-ca >/dev/null 2>&1
printf 'machine:\n  ca:\n    crt: %s\n    key: %s\n' "$(base64 -w0 "$fixture/ca.crt")" "$(base64 -w0 "$fixture/ca.key")" > "$fixture/$NODE_IP.yaml"
printf 'contexts:\n  main:\n    endpoints: [127.0.0.1]\n    crt: old\n    key: old\n' > "$TALOSCONFIG"
cat > "$fixture/bin/op" <<'OP'
#!/usr/bin/env bash
case "$1" in
user) exit 0;;
inject) cat "$3";;
esac
OP
chmod +x "$fixture/bin/op"
export PATH="$fixture/bin:$PATH"
cd "$fixture"
source "$task_root/common.sh"
set +e
source "$rotation_source" rotate-certs
rotation_status=$?
set -e
[[ $rotation_status == 0 ]]
yq -r '.contexts.main.crt' "$TALOSCONFIG" | base64 -d > "$fixture/client.crt"
openssl verify -CAfile "$fixture/ca.crt" "$fixture/client.crt"
openssl x509 -in "$fixture/client.crt" -noout -checkend 31535000
[[ $(stat -c %a "$TALOSCONFIG") == 600 ]]
[[ -z $(ls -A "$TMPDIR") ]]
echo 'PASS: real ops rotation creates a one-year certificate, protects its config, and removes temporary credentials'
