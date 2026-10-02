#!/usr/bin/env bash
# The caller verifies the attached UUID through the UpCloud API first.
# This helper never writes its own mounted root disk.
set -euo pipefail
expected_serial=${1:?Pass the first 20 hex characters of the verified storage UUID, without hyphens}
[[ $expected_serial =~ ^[0-9a-f]{20}$ ]]
[[ $(hostname) == trial-bastion ]]
[[ -b /dev/vdb ]]
[[ $(lsblk -dn -o SERIAL /dev/vdb) == "$expected_serial" ]]
[[ $(cat /sys/block/vdb/size) -eq 83886080 ]]
[[ -z $(lsblk -n -o MOUNTPOINTS /dev/vdb | tr -d '[:space:]') ]]
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=180 install -y wget xz-utils
image=/tmp/talos-1.14.1.raw.xz
wget -q -O "$image" https://factory.talos.dev/image/376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba/v1.14.1/upcloud-amd64.raw.xz
echo "1b2849830f3f6c89a184d0d64e95bdd89c5b01486f6c75f20b1b8c8ac2199621  $image" | sha256sum -c -
expected=$(xz -d -c "$image" | sha256sum | cut -d' ' -f1)
before=$(head -c 11736711168 /dev/vdb | sha256sum | cut -d' ' -f1)
printf 'RAW_IMAGE_SHA256=%s\nDISK_BEFORE_SHA256=%s\n' "$expected" "$before"
if [[ $before != "$expected" ]]; then
    xz -d -c "$image" | dd of=/dev/vdb bs=4M conv=fsync
    blockdev --flushbufs /dev/vdb
fi
actual=$(head -c 11736711168 /dev/vdb | sha256sum | cut -d' ' -f1)
[[ $actual == "$expected" ]]
printf 'DISK_VERIFIED_SHA256=%s\nOFFLINE_IMAGE_VERIFIED\n' "$actual"
