#!/usr/bin/env sh
set -eu

source_file="/data/behavior_packs/Bedrock-Reimagined-Behavior/scripts/imports.js"
output_file="/patched-bedrock-reimagined/imports.js"

if [ "$#" -ge 1 ]; then
  source_file="$1"
fi
if [ "$#" -ge 2 ]; then
  output_file="$2"
fi

expected_source_sha="eb22fc3ef9cf9004d7961f90a110b9ced412a87708fde80df5d93fe0df35ed1a"
expected_output_sha="ce162b231718903eb7feeafcdd20a2cc5ffa0a6019d83e8c0fac1f71a4d5e695"
old_code='if(i.fired=!0,Math.random()>=LH)return;'
new_code='if(i.fired=!0,[...ds.values()].some(e=>t-e.tick>=NH&&e.dimId===a.dimension.id&&(e.ownerId&&TH.getEntity(e.ownerId)?.name==="SpeedMcCheez"||e.hook?.isValid&&e.hook.hasTag("frenzone:no_creature_fishing"))&&(e===i||VA(a.location,e.lastLoc)<=OH))||Math.random()>=LH)return;'
temporary_file="$output_file.tmp"

cleanup() {
  rm -f "$temporary_file"
}
trap cleanup EXIT HUP INT TERM

if [ ! -f "$source_file" ]; then
  echo "Bedrock Reimagined script not found: $source_file" >&2
  exit 1
fi

current_sha="$(sha256sum "$source_file" | awk '{ print $1 }')"
if [ "$current_sha" != "$expected_source_sha" ]; then
  echo "Refusing to patch unexpected Bedrock Reimagined script SHA: $current_sha" >&2
  exit 1
fi

export FRENZONE_OLD_CODE="$old_code"
export FRENZONE_NEW_CODE="$new_code"
perl -0pe '
  BEGIN {
    $old = $ENV{"FRENZONE_OLD_CODE"};
    $new = $ENV{"FRENZONE_NEW_CODE"};
    $count = 0;
  }
  $count += s/\Q$old\E/$new/g;
  END {
    die "Expected exactly one Bedrock Reimagined fishing patch target; found $count\n"
      unless $count == 1;
  }
' "$source_file" > "$temporary_file"

patched_sha="$(sha256sum "$temporary_file" | awk '{ print $1 }')"
if [ "$patched_sha" != "$expected_output_sha" ]; then
  echo "Patched Bedrock Reimagined script has unexpected SHA: $patched_sha" >&2
  exit 1
fi

chmod 0444 "$temporary_file"
mv "$temporary_file" "$output_file"
trap - EXIT HUP INT TERM

echo "Prepared guarded Bedrock Reimagined fishing patch."
