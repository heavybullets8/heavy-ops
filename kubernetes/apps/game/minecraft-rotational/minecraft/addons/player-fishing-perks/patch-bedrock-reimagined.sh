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

expected_source_sha="1422adc4388c34366d49ba961a4f35ef417c84c3eb1d45016dd07c318c6f25d5"
expected_output_sha="0482053c61c788aeeb449e0a8e04d1fe2da9ea5a316926a091ea076793b2018c"
old_code='if(i.fired=!0,Math.random()>=kj)return;'
new_code='if(i.fired=!0,[...ps.values()].some(e=>t-e.tick>=Pj&&e.dimId===a.dimension.id&&(e.ownerId&&Cj.getEntity(e.ownerId)?.name==="SpeedMcCheez"||e.hook?.isValid&&e.hook.hasTag("frenzone:no_creature_fishing"))&&(e===i||mE(a.location,e.lastLoc)<=Sj))||Math.random()>=kj)return;'
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
