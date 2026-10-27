#!/usr/bin/env sh
set -eu

source_file="${1:-/data/behavior_packs/Crops-Farms-Behavior/scripts/crops/sgs_farm_treemanager.js}"
backup_file="$source_file.bak"
expected_source_sha="10dc8635d099311d4f062150a0c4629f54751830d5d7e81124c6f0c472fa6340"
expected_patched_sha="a266dab96705c198d80564b5052a2a34c287dc8184452453a94d19e16940e3ed"

checksum() {
  sha256sum "$1" | awk '{ print $1 }'
}

current_sha="$(checksum "$source_file")"
case "$current_sha" in
  "$expected_source_sha"|"$expected_patched_sha") ;;
  *)
    echo "Refusing to patch unexpected Crops & Farms script SHA: $current_sha" >&2
    exit 1
    ;;
esac

if [ -e "$backup_file" ]; then
  if [ "$(checksum "$backup_file")" != "$expected_source_sha" ]; then
    echo "Existing .bak does not match the original script; leaving both files unchanged." >&2
    exit 1
  fi
elif [ "$current_sha" = "$expected_source_sha" ]; then
  cp -p "$source_file" "$backup_file"
  if [ "$(checksum "$backup_file")" != "$expected_source_sha" ]; then
    echo "Original .bak verification failed; leaving source unchanged." >&2
    exit 1
  fi
else
  echo "Patched script has no original .bak; refusing to create a backup from patched code." >&2
  exit 1
fi

if [ "$current_sha" = "$expected_patched_sha" ]; then
  echo "Crops & Farms tree-growth fix already installed; original .bak verified."
  exit 0
fi

temporary_file="$(mktemp "$source_file.tmp.XXXXXX")"
cleanup() {
  rm -f "$temporary_file"
}
trap cleanup EXIT HUP INT TERM
cp -p "$source_file" "$temporary_file"

export FRENZONE_OLD_CODE='                        if (!dimension.getBlock({ x: location.x + x - offset, y: location.y + y, z: location.z + z - offset }).isAir) isAir = false;'
export FRENZONE_NEW_CODE='                        const targetBlock = dimension.getBlock({ x: location.x + x - offset, y: location.y + y, z: location.z + z - offset });
                        // Defer growth until the full tree area is available for inspection.
                        if (targetBlock === undefined) return false;
                        if (!targetBlock.isAir) isAir = false;'
perl -0pe '
  BEGIN {
    $old = $ENV{"FRENZONE_OLD_CODE"};
    $new = $ENV{"FRENZONE_NEW_CODE"};
    $count = 0;
  }
  $count += s/\Q$old\E/$new/g;
  END {
    die "Expected exactly one Crops & Farms tree-growth patch target; found $count\n"
      unless $count == 1;
  }
' "$source_file" > "$temporary_file"

if [ "$(checksum "$temporary_file")" != "$expected_patched_sha" ]; then
  echo "Patched Crops & Farms script has an unexpected SHA; original left unchanged." >&2
  exit 1
fi

mv "$temporary_file" "$source_file"
trap - EXIT HUP INT TERM
echo "Installed Crops & Farms tree-growth fix; original preserved at $backup_file"
