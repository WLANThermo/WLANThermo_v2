#!/bin/bash
# Usage: pit_run.sh <git-rev|WORKTREE> <outdir>
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
PY=${PYTHON:-python3}
REV=$1
OUT=$(realpath -m "$2")
rm -rf "$OUT" && mkdir -p "$OUT"
SRC=$OUT/src
if [ "$REV" = WORKTREE ]; then
    cp -r "$REPO/src" "$SRC"
else
    mkdir -p "$SRC.tmp" && git -C "$REPO" archive "$REV" src | tar -x -C "$SRC.tmp" && mv "$SRC.tmp/src" "$SRC" && rmdir "$SRC.tmp"
fi
for scenario in fan_curve fan_pwm_pid servo_lid io_inverted io_pwm_pid damper_mini pit2_changes bad_values damper_v3 curve_to_pid sigterm unknown_instance; do
    VAR=$(mktemp -d)
    unshare -rm bash -c "mount --bind '$VAR' /var && exec '$PY' -I -W ignore '$HERE/pit_inner.py' '$SRC' '$OUT/$scenario' '$scenario' '$REPO/software/var/www/conf'" \
        > "$OUT/$scenario.stdout" 2>&1 || { echo "scenario $scenario failed:"; tail -20 "$OUT/$scenario.stdout"; }
    cp "$VAR/log/WLANThermo.log" "$OUT/$scenario.daemon.log" 2>/dev/null || true
    rm -rf "$VAR"
done
rm -rf "$SRC"
echo "done: $OUT"
